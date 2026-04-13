from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
import pandas as pd
import re
import nltk
from nltk.corpus import stopwords

# Скачиваем русские стоп-слова (делается один раз)
try:
    nltk.data.find('corpora/stopwords')
except LookUpError:
    nltk.download('stopwords')

stop_words = stopwords.words('russian')


class TextProcessor:
    @staticmethod
    def clean_text(text):
        if not text or not isinstance(text, str):
            return ""
        text = text.lower()
        # Удаляем ссылки
        text = re.sub(r'https?://\S+|www\.\S+', '', text)
        # Удаляем спецсимволы и цифры, оставляем только буквы и пробелы
        text = re.sub(r'[^а-яёa-z\s]', '', text)
        # Удаляем лишние пробелы
        text = " ".join(text.split())
        return text

    def get_top_keywords(self, texts, n=10):
        """Выделение топ-N ключевых слов через TF-IDF"""
        # ИСПРАВЛЕННАЯ ПРОВЕРКА:
        if texts is None or len(texts) == 0:
            return []

        # Очищаем тексты перед анализом
        cleaned_texts = texts.apply(self.clean_text)

        # Проверяем, не пустые ли тексты после очистки
        if cleaned_texts.str.strip().replace('', pd.NA).dropna().empty:
            return []

        try:
            vectorizer = TfidfVectorizer(stop_words=stop_words, max_features=n)
            tfidf_matrix = vectorizer.fit_transform(cleaned_texts)
            feature_names = vectorizer.get_feature_names_out()
            return list(feature_names)
        except:
            return []

    def cluster_messages(self, df, n_clusters=3):
        """Разбиение сообщений на темы"""
        if df is None or len(df) < n_clusters or len(df) < 2:
            return df

        try:
            vectorizer = TfidfVectorizer(stop_words=stop_words)
            cleaned_texts = df['text'].apply(self.clean_text)

            # Проверка на пустые данные после очистки
            if cleaned_texts.str.strip().replace('', pd.NA).dropna().empty:
                df['cluster'] = "Без темы"
                return df

            X = vectorizer.fit_transform(cleaned_texts)

            # Количество кластеров не может быть больше количества документов
            n_clusters = min(n_clusters, X.shape[0])

            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            df['cluster'] = kmeans.fit_predict(X)
            df['cluster'] = df['cluster'].apply(lambda x: f"Тема {x + 1}")
        except Exception as e:
            print(f"Ошибка кластеризации: {e}")
            df['cluster'] = "Анализ недоступен"

        return df