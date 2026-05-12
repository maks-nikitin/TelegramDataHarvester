from sklearn.feature_extraction.text import CountVectorizer
import pandas as pd
import re
import nltk
from nltk.corpus import stopwords
import torch
from transformers import pipeline
import json
import os
import time

# Загружаем "стоп-слова" (предлоги, союзы), которые ИИ будет игнорировать при анализе частотности
try:
    nltk.download('stopwords', quiet=True)
except:
    pass

stop_words = stopwords.words('russian')


class TextProcessor:
    """
    Класс для интеллектуальной обработки текста.
    Использует нейросети для классификации и морфологический анализ для статистики.
    """

    def __init__(self):
        # 1. Загрузка категорий из JSON-конфига (чтобы темы можно было менять без правки кода)
        config_path = os.path.join(os.path.dirname(__file__), '../../config/categories.json')
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                # labels — список тем (Спорт, Политика и т.д.)
                self.labels = [k.title() for k in config_data['categories'].keys() if k != "ОБЩЕСТВО"]
                self.default_label = config_data.get('default_category', "ОБЩЕСТВО")
        except Exception as e:
            self.labels = ["Спорт", "Политика", "Экономика"]
            self.default_label = "ОБЩЕСТВО"

        # 2. Инициализация нейросети DeBERTa
        # Проверяем, есть ли видеокарта (GPU) для ускорения. Если нет — используем процессор (CPU).
        device = 0 if torch.cuda.is_available() else -1
        try:
            # Используем модель "Zero-Shot Classification".
            # Она умеет определять тему текста, даже если её специально не учили на этих темах.
            self.classifier = pipeline(
                "zero-shot-classification",
                model="MoritzLaurer/mDeBERTa-v3-base-mnli-xnli",
                device=device
            )
        except Exception as e:
            self.classifier = None

    def clean_extract_essence(self, text):
        """Очистка текста от мусора (ссылок, кнопок), чтобы ИИ видел только суть"""
        if not text: return ""
        # Удаляем ссылки http/https/www
        text = re.sub(r'https?://\S+|www\.\S+', '', text)
        # Отрезаем типичные "хвосты" постов в ТГ (типа "Подробнее в канале...")
        parts = re.split(r'Подробности|Подробнее|❤️|💬|#|t.me', text)
        text = parts[0] if len(parts[0].strip()) > 15 else text
        # Оставляем только буквы и знаки препинания
        text = re.sub(r'[^\w\s\.\,\!\?\-]', '', text)
        # Убираем лишние пробелы и переносы строк
        return " ".join(text.split()).strip()

    def cluster_messages(self, df):
        """Процесс присвоения категории (классификация) для каждого поста"""
        if df is None or df.empty: return df
        df_result = df.copy()

        # Шаблон вопроса для нейросети (NLI-подход)
        hypothesis = "Эта новость посвящена теме {}."

        print(f"\n--- [AI] Начинаю анализ {len(df)} новых постов ---")
        total_ai_start = time.time()

        for index, row in df_result.iterrows():
            post_start = time.time()
            raw_text = row.get('text', '')
            cleaned = self.clean_extract_essence(raw_text)

            # Если пост слишком короткий (меньше 15 букв), нейросеть может ошибиться
            if len(cleaned) < 15:
                df_result.at[index, 'cluster'] = self.default_label
                continue

            if self.classifier:
                try:
                    # Подаем в нейросеть только первые 200 символов (самое важное в новости всегда в начале)
                    # Это ускоряет работу в 2-3 раза.
                    res = self.classifier(cleaned[:200], self.labels, multi_label=False, hypothesis_template=hypothesis)

                    label = res['labels'][0].upper()  # Самая вероятная тема
                    score = res['scores'][0]  # Коэффициент уверенности (0.0 до 1.0)

                    # Если нейросеть уверена больше чем на 30%, ставим тему, иначе — в "Общество"
                    theme = label if score > 0.30 else self.default_label
                    df_result.at[index, 'cluster'] = theme

                    duration = time.time() - post_start
                    # Вывод подробностей в консоль (как ты просил для демо)
                    print(f" Пост {index + 1}: {theme} (Уверенность: {score:.4f}, Время: {duration:.2f} сек)")
                except:
                    df_result.at[index, 'cluster'] = "НОВОСТИ"

        print(f"--- [AI] Завершено за {time.time() - total_ai_start:.2f} сек ---\n")
        return df_result

    def get_top_ngram_counts(self, texts, n=15):
        """Анализ частотности слов (построение графика ключевых фраз)"""
        if texts is None or len(texts) == 0: return pd.DataFrame()
        try:
            # Используем библиотеку pymorphy3 для приведения слов к начальной форме (лемматизация)
            try:
                import pymorphy3 as pm
                morph = pm.MorphAnalyzer()
            except:
                morph = None

            # Список мусорных слов, которые часто встречаются в ссылках и технических частях ТГ
            tg_junk = {
                'https', 'http', 'www', 'com', 'ru', 'org', 'by', 'net', 'me', 'tg', 'co',
                'telegram', 'channel', 'подписывайтесь', 'канал', 'это', 'который', 'свой'
            }
            extended_stop_words = set(stop_words).union(tg_junk)

            def advanced_clean_and_lemmatize(t):
                """Превращает 'футболистами' в 'футболист', удаляет ссылки и мусор"""
                if not isinstance(t, str): return ""
                t = t.lower()
                # Удаляем домены и почты полностью
                t = re.sub(r'https?://\S+|www\.\S+|t\.me/\S+', ' ', t)
                t = re.sub(r'\b\w+\.(by|ru|com|org|net|me)\b', ' ', t)
                # Оставляем только буквы
                t = re.sub(r'[^а-яёa-z\s]', ' ', t)

                words = t.split()
                lemmas = []
                for word in words:
                    if len(word) < 3: continue  # Игнорируем слишком короткие слова

                    # Процесс лемматизации
                    lemma = morph.parse(word)[0].normal_form if morph else word

                    if lemma not in extended_stop_words:
                        lemmas.append(lemma)
                return " ".join(lemmas)

            cleaned_texts = texts.apply(advanced_clean_and_lemmatize)

            # CountVectorizer считает, сколько раз встретилось каждое слово и фраза из 2-х слов (ngram_range 1-2)
            vectorizer = CountVectorizer(ngram_range=(1, 2), max_features=n)
            X = vectorizer.fit_transform(cleaned_texts)

            if X.shape[1] == 0: return pd.DataFrame()

            return pd.DataFrame({
                'phrase': vectorizer.get_feature_names_out(),
                'count': X.sum(axis=0).A1
            }).sort_values(by='count', ascending=False)

        except Exception as e:
            print(f"Ошибка n-грамм: {e}")
            return pd.DataFrame()