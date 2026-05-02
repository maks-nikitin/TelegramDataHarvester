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
        print("--- [SYSTEM] Инициализация нейросети... ---")
        device = 0 if torch.cuda.is_available() else -1
        try:
            self.classifier = pipeline(
                "zero-shot-classification",
                model="MoritzLaurer/mDeBERTa-v3-base-mnli-xnli",
                device=device
            )
            print(f"--- [SYSTEM] ИИ готов (Device: {'GPU' if device == 0 else 'CPU'}) ---")
        except Exception as e:
            self.classifier = None
            print(f"--- [ERROR] ИИ не загружен: {e} ---")

        # СОКРАЩЕННЫЙ СПИСОК (Для скорости и точности)
        self.labels = [
            "Политика",
            "Экономика",
            "Криминал",
            "Происшествия и ЧП",
            "Спорт",
            "Образование",
            "Сельское хозяйство",
            "Культура",
            "Погода"
        ]

        # УСИЛЕННЫЙ СЛОВАРЬ (Чтобы ловить Образование и Пожары мгновенно)
        self.fast_rules = {
            "ПОГОДА": ["погода", "прогноз", "температура", "градус", "осадки", "белгидромет"],
            "ОБРАЗОВАНИЕ": ["вуз", "студент", "абитуриент", "школа", "экзамен", "бюджетных мест", "обучение",
                            "университет"],
            "ПРОИСШЕСТВИЯ И ЧП": ["пожар", "мчс", "спасатели", "возгорание", "дтп", "авария", "ликвидировали"],
            "СЕЛЬСКОЕ ХОЗЯЙСТВО": ["свиновод", "аграрный", "посевная", "фермер", "сельхоз"],
            "КРИМИНАЛ": ["похитил", "украл", "мошенник", "задержан", "розыск", "кража", "миллиция"],
            "СПОРТ": ["матч", "чемпионат", "фитнес", "бодибилдинг", "турнир"]
        }

    def clean_full(self, text):
        if not text: return ""
        # Отрезаем ссылки и мусор
        text = re.split(r'Подробности|Подробнее|❤️|\[Inst\]|\[TikTok\]|http|💬|#|t.me', text)[0]
        text = re.sub(r'[^\w\s\.\,\!\?\-]', '', text)
        text = " ".join(text.split())
        return text

    def _fast_check(self, text):
        text_lower = text.lower()
        for label, keywords in self.fast_rules.items():
            if any(word in text_lower for word in keywords):
                return label
        return None

    def cluster_messages(self, df):
        if df is None or df.empty: return df
        df_result = df.copy()

        print(f"\n=== АНАЛИЗ {len(df)} СООБЩЕНИЙ ===")

        for index, row in df_result.iterrows():
            raw_text = row.get('text', '')
            cleaned = self.clean_full(raw_text)

            # 1. Быстрый фильтр (Словарь)
            theme = self._fast_check(cleaned)

            if theme:
                print(f"-> [СЛОВАРЬ] {cleaned[:50]}... => {theme}")

            # 2. Нейросеть (если словарь молчит)
            if not theme and self.classifier:
                try:
                    # Берем только первые 150 символов для супер-скорости
                    res = self.classifier(cleaned[:150], self.labels, multi_label=False)

                    label = res['labels'][0].upper()
                    score = res['scores'][0]

                    # Пишем отладку в консоль PyCharm
                    print(f"-> [ИИ {score:.2f}] {cleaned[:50]}... => {label}")

                    # Убираем жесткий порог, чтобы не всё шло в ОБЩЕСТВО
                    if score > 0.25:
                        theme = label
                    else:
                        theme = "ОБЩЕСТВО"
                except Exception as e:
                    theme = "НОВОСТИ"
            elif not theme:
                theme = "ОБЩЕСТВО"

            df_result.at[index, 'cluster'] = theme

        print("=== АНАЛИЗ ЗАВЕРШЕН ===\n")
        return df_result

    def get_top_ngram_counts(self, texts, n=15):
        if texts is None or len(texts) == 0: return pd.DataFrame()
        try:
            def simple_clean(t):
                t = self.clean_full(t).lower()
                t = re.sub(r'[^а-яёa-z\s]', ' ', t)
                return " ".join(t.split())

            cleaned = texts.apply(simple_clean)
            vectorizer = CountVectorizer(stop_words=stop_words, ngram_range=(1, 2), max_features=n)
            X = vectorizer.fit_transform(cleaned)
            return pd.DataFrame({'phrase': vectorizer.get_feature_names_out(), 'count': X.sum(axis=0).A1}).sort_values(
                by='count', ascending=False)
        except:
            return pd.DataFrame()