from sklearn.feature_extraction.text import CountVectorizer
import pandas as pd
import re
import nltk
from nltk.corpus import stopwords
import torch
from transformers import pipeline

try:
    nltk.download('stopwords', quiet=True)
except:
    pass

stop_words = stopwords.words('russian')


class TextProcessor:
    def __init__(self):
        print("--- [SYSTEM] Инициализация нейросетевого ядра... ---")
        device = 0 if torch.cuda.is_available() else -1
        try:
            # Используем модель для Zero-Shot классификации
            self.classifier = pipeline(
                "zero-shot-classification",
                model="MoritzLaurer/mDeBERTa-v3-base-mnli-xnli",
                device=device
            )
            print(f"--- [SYSTEM] ИИ готов (Device: {'GPU' if device == 0 else 'CPU'}) ---")
        except Exception as e:
            self.classifier = None
            print(f"--- [ERROR] ИИ не загружен: {e} ---")

        # Уточненный список категорий для нейросети
        self.labels = [
            "Власть и Политика",
            "Экономика и Финансы",
            "Криминал и Правосудие",
            "Происшествия и ЧП",
            "Спорт",
            "Образование и Наука",
            "Сельское хозяйство",
            "Погода",
            "Культура и Искусство",
            "Здравоохранение",
            "Технологии и IT"
        ]

    def clean_extract_essence(self, text):
        """Очистка текста: убираем шум, чтобы ИИ видел только суть"""
        if not text: return ""
        # 1. Отрезаем ссылки и социальные сети
        text = re.split(r'Подробности|Подробнее|❤️|\[Inst\]|\[TikTok\]|http|💬|#|t.me', text)[0]
        # 2. Убираем спецсимволы, оставляя знаки препинания для контекста
        text = re.sub(r'[^\w\s\.\,\!\?\-]', '', text)
        # 3. Убираем лишние пробелы
        text = " ".join(text.split())
        return text.strip()

    def cluster_messages(self, df):
        """Классификация сообщений исключительно средствами ИИ"""
        if df is None or df.empty: return df
        df_result = df.copy()

        # Шаблон гипотезы для повышения точности
        hypothesis = "Эта новость посвящена теме {}."

        print(f"\n--- [AI] Начинаю анализ {len(df)} сообщений ---")

        for index, row in df_result.iterrows():
            raw_text = row.get('text', '')
            cleaned = self.clean_extract_essence(raw_text)

            if len(cleaned) < 15:
                df_result.at[index, 'cluster'] = "ОБЩЕСТВО"
                continue

            if self.classifier:
                try:
                    # Подаем в ИИ только смысловое ядро (первые 200 символов)
                    # Это в разы ускоряет работу без потери точности
                    res = self.classifier(
                        cleaned[:200],
                        self.labels,
                        multi_label=False,
                        hypothesis_template=hypothesis
                    )

                    label = res['labels'][0].upper()
                    score = res['scores'][0]

                    # Логика: если ИИ уверен более чем на 30%, ставим тему
                    if score > 0.30:
                        theme = label
                    else:
                        theme = "ОБЩЕСТВО"

                    print(f"-> [CONF: {score:.2f}] {cleaned[:40]}... => {theme}")

                except Exception as e:
                    print(f"Ошибка классификации: {e}")
                    theme = "НОВОСТИ"
            else:
                theme = "БЕЗ АНАЛИЗА"

            df_result.at[index, 'cluster'] = theme

        print("--- [AI] Анализ завершен ---\n")
        return df_result

    def get_top_ngram_counts(self, texts, n=15):
        """Статистический анализ частотности слов"""
        if texts is None or len(texts) == 0: return pd.DataFrame()
        try:
            def simple_clean(t):
                t = t.lower()
                t = re.sub(r'[^а-яёa-z\s]', ' ', t)
                return " ".join(t.split())

            cleaned = texts.apply(simple_clean)
            vectorizer = CountVectorizer(stop_words=stop_words, ngram_range=(1, 2), max_features=n)
            X = vectorizer.fit_transform(cleaned)
            return pd.DataFrame({'phrase': vectorizer.get_feature_names_out(), 'count': X.sum(axis=0).A1}).sort_values(
                by='count', ascending=False)
        except:
            return pd.DataFrame()