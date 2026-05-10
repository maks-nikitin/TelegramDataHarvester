from sklearn.feature_extraction.text import CountVectorizer
import pandas as pd
import re
import nltk
from nltk.corpus import stopwords
import torch
from transformers import pipeline
import json
import os

# Загружаем стоп-слова (предлоги, союзы), которые нужно игнорировать при анализе частотности
try:
    nltk.download('stopwords', quiet=True)
except:
    pass

stop_words = stopwords.words('russian')


class TextProcessor:
    """
    Интеллектуальное ядро системы.
    Отвечает за классификацию по темам и качественный анализ ключевых фраз.
    """

    def __init__(self):
        # 1. Загрузка конфигурации тем из JSON (чтобы легко менять категории анализа)
        config_path = os.path.join(os.path.dirname(__file__), '../../config/categories.json')
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                self.labels = [k.title() for k in config_data['categories'].keys() if k != "ОБЩЕСТВО"]
                self.default_label = config_data.get('default_category', "ОБЩЕСТВО")
        except Exception as e:
            self.labels = ["Спорт", "Политика", "Экономика"]
            self.default_label = "ОБЩЕСТВО"

        # 2. Инициализация ИИ (Zero-Shot модель)
        device = 0 if torch.cuda.is_available() else -1
        try:
            self.classifier = pipeline(
                "zero-shot-classification",
                model="MoritzLaurer/mDeBERTa-v3-base-mnli-xnli",
                device=device
            )
        except Exception as e:
            self.classifier = None

    def clean_extract_essence(self, text):
        """Очистка текста специально для нейросети"""
        if not text: return ""
        # Удаляем ссылки
        text = re.sub(r'https?://\S+|www\.\S+', '', text)
        # Отрезаем мусорные фразы в конце постов
        parts = re.split(r'Подробности|Подробнее|❤️|💬|#|t.me', text)
        text = parts[0] if len(parts[0].strip()) > 15 else text
        # Оставляем буквы и знаки препинания
        text = re.sub(r'[^\w\s\.\,\!\?\-]', '', text)
        return " ".join(text.split()).strip()

    def cluster_messages(self, df):
        """Процесс присвоения категорий постам с помощью ИИ"""
        if df is None or df.empty: return df
        df_result = df.copy()
        hypothesis = "Эта новость посвящена теме {}."

        for index, row in df_result.iterrows():
            cleaned = self.clean_extract_essence(row.get('text', ''))
            if len(cleaned) < 15:
                df_result.at[index, 'cluster'] = self.default_label
                continue

            if self.classifier:
                try:
                    res = self.classifier(cleaned[:200], self.labels, multi_label=False, hypothesis_template=hypothesis)
                    label = res['labels'][0].upper()
                    score = res['scores'][0]
                    df_result.at[index, 'cluster'] = label if score > 0.30 else self.default_label
                except:
                    df_result.at[index, 'cluster'] = "НОВОСТИ"
        return df_result

    def get_top_ngram_counts(self, texts, n=15):
        """
        ФИНАЛЬНЫЙ АЛГОРИТМ АНАЛИЗА КЛЮЧЕВЫХ СЛОВ.
        Здесь происходит лемматизация и фильтрация мусора.
        """
        if texts is None or len(texts) == 0: return pd.DataFrame()
        try:
            # Подключаем pymorphy3 для лемматизации (новости -> новость)
            try:
                import pymorphy3 as pm
                morph = pm.MorphAnalyzer()
            except:
                morph = None

            # Расширенный список 'мусорных' слов, которые часто встречаются в ссылках Telegram
            tg_junk = {
                'https', 'http', 'www', 'com', 'ru', 'org', 'by', 'net', 'me', 'tg', 'co',
                'telegram', 'channel', 'подписывайтесь', 'канал', 'читать', 'это', 'который',
                'свой', 'наш', 'ваш', 'его', 'ее', 'их', 'также', 'быть', 'мочь', 'новость',
                'grodno', 'minsk', 'news', 'grodnonews'
            }
            extended_stop_words = set(stop_words).union(tg_junk)

            def advanced_clean_and_lemmatize(t):
                """Глубокая очистка и приведение слов к начальной форме"""
                if not isinstance(t, str): return ""
                t = t.lower()
                # 1. Удаляем ссылки, почты, домены полностью
                t = re.sub(r'https?://\S+|www\.\S+|t\.me/\S+', ' ', t)
                t = re.sub(r'\b\w+\.(by|ru|com|org|net|me)\b', ' ', t)
                # 2. Оставляем только буквы
                t = re.sub(r'[^а-яёa-z\s]', ' ', t)

                words = t.split()
                lemmas = []
                for word in words:
                    if len(word) < 3: continue  # Игнорируем предлоги и союзы < 3 букв

                    # Лемматизируем: 'футболистами' -> 'футболист'
                    lemma = morph.parse(word)[0].normal_form if morph else word

                    # Если слово не мусорное - добавляем в список
                    if lemma not in extended_stop_words:
                        lemmas.append(lemma)
                return " ".join(lemmas)

            # Обрабатываем тексты
            cleaned_texts = texts.apply(advanced_clean_and_lemmatize)

            # Настраиваем векторизатор: ищем слова (1) и фразы из двух слов (2)
            vectorizer = CountVectorizer(ngram_range=(1, 2), max_features=n)
            X = vectorizer.fit_transform(cleaned_texts)

            if X.shape[1] == 0: return pd.DataFrame()

            # Возвращаем данные для графика в Streamlit
            return pd.DataFrame({
                'phrase': vectorizer.get_feature_names_out(),
                'count': X.sum(axis=0).A1
            }).sort_values(by='count', ascending=False)

        except Exception as e:
            print(f"Ошибка анализа ключевых слов: {e}")
            return pd.DataFrame()