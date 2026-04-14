from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from sklearn.cluster import KMeans
import pandas as pd
import re
import nltk
from nltk.corpus import stopwords
import torch
from transformers import pipeline

# Загрузка стоп-слов
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')

stop_words = stopwords.words('russian')


class TextProcessor:
    def __init__(self):
        # 1. Инициализация нейросети для определения тем (Пункт 3 ТЗ)
        # Модель mDeBERTa хорошо понимает русский язык
        print("Загрузка нейросети для анализа тем (может занять время)...")
        device = 0 if torch.cuda.is_available() else -1
        self.classifier = pipeline(
            "zero-shot-classification",
            model="MoritzLaurer/mDeBERTa-v3-base-mnli-xnli",
            device=device
        )
        # Список категорий, которые нейросеть будет присваивать темам
        self.labels = ["политика", "экономика", "криптовалюты", "технологии", "развлечения", "спорт", "здоровье",
                       "образование", "казино и скам"]

    @staticmethod
    def clean_text(text):
        if not text or not isinstance(text, str):
            return ""
        text = text.lower()
        text = re.sub(r'https?://\S+|www\.\S+', '', text)
        text = re.sub(r'[^а-яёa-z\s]', '', text)
        text = " ".join(text.split())
        return text

    def get_top_ngram_counts(self, texts, n=10, ngram_range=(1, 2)):
        """Подсчет частоты употребления слов и фраз (Пункт 1 ТЗ)"""
        if texts is None or len(texts) == 0:
            return pd.DataFrame(columns=['phrase', 'count'])

        cleaned_texts = texts.apply(self.clean_text)
        cleaned_texts = cleaned_texts[cleaned_texts.str.strip() != ""]

        if cleaned_texts.empty:
            return pd.DataFrame(columns=['phrase', 'count'])

        # Используем CountVectorizer для простого подсчета частоты
        vectorizer = CountVectorizer(stop_words=stop_words, ngram_range=ngram_range, max_features=n)
        X = vectorizer.fit_transform(cleaned_texts)

        # Суммируем появления каждого слова
        words = vectorizer.get_feature_names_out()
        counts = X.sum(axis=0).A1

        df_counts = pd.DataFrame({'phrase': words, 'count': counts})
        return df_counts.sort_values(by='count', ascending=False)

    def cluster_messages(self, df, n_clusters=3):
        """Кластеризация и автоматическое именование тем нейросетью"""
        if df is None or len(df) < n_clusters or len(df) < 2:
            return df

        # Сначала делаем математическую кластеризацию (K-Means)
        vectorizer = TfidfVectorizer(stop_words=stop_words, ngram_range=(1, 2))
        cleaned_texts = df['text'].apply(self.clean_text)
        X = vectorizer.fit_transform(cleaned_texts)

        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        df['cluster_id'] = kmeans.fit_predict(X)

        # Теперь для каждого кластера просим нейросеть придумать название
        cluster_names = {}
        for i in range(n_clusters):
            # Берем тексты, попавшие в этот кластер
            cluster_texts = df[df['cluster_id'] == i]['text'].tolist()
            if cluster_texts:
                # Берем кусочек текста для нейросети (чтобы работало быстрее)
                sample_text = " ".join(cluster_texts[:3])[:400]

                # Нейросеть выбирает лучшую категорию из self.labels
                res = self.classifier(sample_text, self.labels, multi_label=False)
                cluster_names[i] = res['labels'][0].upper()
            else:
                cluster_names[i] = f"ТЕМА {i + 1}"

        # Заменяем ID кластеров на красивые названия
        df['cluster'] = df['cluster_id'].map(cluster_names)
        return df