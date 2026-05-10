from sklearn.feature_extraction.text import CountVectorizer
import pandas as pd
import re
import nltk
from nltk.corpus import stopwords
import torch
from transformers import pipeline
import json
import os

try:
    nltk.download('stopwords', quiet=True)
except:
    pass

stop_words = stopwords.words('russian')


class TextProcessor:
    def __init__(self):
        # --- [НОВОЕ] Загрузка категорий из файла ---
        config_path = os.path.join(os.path.dirname(__file__), '../../config/categories.json')
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                # Берем ключи (названия тем) для ИИ
                self.labels = [k.title() for k in config_data['categories'].keys() if k != "ОБЩЕСТВО"]
                self.default_label = config_data.get('default_category', "ОБЩЕСТВО")
        except Exception as e:
            print(f"--- [WARNING] Не удалось загрузить категории: {e}. Использую дефолтные. ---")
            self.labels = ["Спорт", "Политика", "Экономика"]  # Фолбэк
            self.default_label = "ОБЩЕСТВО"

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

        # Сначала аккуратно удаляем явные URL, чтобы не ломать структуру текста
        text = re.sub(r'https?://\S+|www\.\S+', '', text)

        # 1. Отрезаем "хвосты" с призывами к действию и ссылками
        parts = re.split(r'Подробности|Подробнее|❤️|\[Inst\]|\[TikTok\]|💬|#|t.me', text)
        # Если после отрезания текст остался нормальной длины - берем его, иначе исходный (без ссылок)
        text = parts[0] if len(parts[0].strip()) > 15 else text

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
                df_result.at[index, 'cluster'] = self.default_label
                continue

            if self.classifier:
                try:
                    # Подаем в ИИ только смысловое ядро (первые 200 символов)
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
        """Продвинутый анализ частотности слов с лемматизацией и фильтрацией мусора"""
        if texts is None or len(texts) == 0: return pd.DataFrame()
        try:
            # Инициализируем лемматизатор русского языка
            try:
                import pymorphy3 as pm
                morph = pm.MorphAnalyzer()
            except ImportError:
                morph = None
                print("--- [WARNING] pymorphy3 не установлен! Лемматизация отключена. ---")

            # Расширенный список мусорных слов (Telegram-специфика и общие слова-паразиты)
            tg_web_stopwords = {
                'https', 'http', 'www', 'com', 'ru', 'org', 'by', 'net', 'me', 'tg', 'co',
                'telegram', 'channel', 'подписывайтесь', 'канал', 'читать', 'подробности',
                'это', 'всё', 'который', 'свой', 'наш', 'ваш', 'его', 'ее', 'их', 'также',
                'быть', 'мочь', 'очень', 'новость', 'сообщение', 'фото', 'видео', 'пост',
                'самый', 'главный', 'город', 'область', 'район', 'беларусь', 'россия',
                'grodno', 'minsk', 'grodnonews', 'news'  # Локальные мусорные слова из ссылок
            }
            extended_stop_words = set(stop_words).union(tg_web_stopwords)

            def advanced_clean_and_lemmatize(t):
                if not isinstance(t, str): return ""

                # 1. К нижнему регистру
                t = t.lower()

                # 2. Полностью удаляем ссылки, юзернеймы и хэштеги
                t = re.sub(r'https?://\S+|www\.\S+|t\.me/\S+', ' ', t)
                t = re.sub(r'[@#]\w+', ' ', t)
                # Удаляем почты и домены вроде "grodnonews.by"
                t = re.sub(r'\b\w+\.(by|ru|com|org|net|me|info)\b', ' ', t)

                # 3. Оставляем только буквы
                t = re.sub(r'[^а-яёa-z\s]', ' ', t)

                words = t.split()
                processed_words = []

                for word in words:
                    # Игнорируем слишком короткие слова (< 3 букв)
                    if len(word) < 3:
                        continue

                    # Приводим к начальной форме (лемматизируем)
                    if morph:
                        lemma = morph.parse(word)[0].normal_form
                    else:
                        lemma = word

                    # Проверяем на стоп-слова
                    if lemma not in extended_stop_words:
                        processed_words.append(lemma)

                return " ".join(processed_words)

            cleaned = texts.apply(advanced_clean_and_lemmatize)

            # Настраиваем векторизатор на поиск слов и словосочетаний (1 и 2 слова)
            vectorizer = CountVectorizer(ngram_range=(1, 2), max_features=n)
            X = vectorizer.fit_transform(cleaned)

            # Если после жесткой очистки ничего не осталось
            if X.shape[1] == 0:
                return pd.DataFrame()

            return pd.DataFrame({
                'phrase': vectorizer.get_feature_names_out(),
                'count': X.sum(axis=0).A1
            }).sort_values(by='count', ascending=False)

        except Exception as e:
            print(f"Ошибка n-грамм: {e}")
            return pd.DataFrame()