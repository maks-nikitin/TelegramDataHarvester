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
        print("Загрузка нейросети для анализа тем...")
        device = 0 if torch.cuda.is_available() else -1
        try:
            self.classifier = pipeline(
                "zero-shot-classification",
                model="MoritzLaurer/mDeBERTa-v3-base-mnli-xnli",
                device=device
            )
        except Exception as e:
            print(f"Ошибка ИИ: {e}")
            self.classifier = None

        # Улучшенный список категорий для нейронки
        self.labels = [
            "политика", "экономика", "криптовалюты", "технологии",
            "развлечения", "спорт", "здоровье", "образование",
            "происшествия", "погода", "культура", "общество"
        ]

        # ГИПЕР-РАСШИРЕННЫЙ ФИЛЬТР (Для моментальной и точной работы)
        self.fast_rules = {
            "ПОГОДА": ["погода", "прогноз", "температура", "градус", "дождь", "осадки", "солнечно", "ветер", "синоптик",
                       "белгидромет"],
            "СПОРТ": ["бодибилдинг", "фитнес", "атлет", "матч", "футбол", "хоккей", "турнир", "чемпион", "олимпиада",
                      "тренировка"],
            "ПОЛИТИКА": ["лукашенко", "президент", "закон", "указ", "депутат", "правительство", "совет республики",
                         "выборы"],
            "ЭКОНОМИКА": ["инфляция", "бюджет", "налог", "финансы", "ввп", "предприятие", "производство", "экспорт",
                          "импорт"],
            "ПРОИСШЕСТВИЯ": ["мвд", "гаи", "ск", "суд", "задержан", "дтп", "авария", "криминал", "милиция", "пожар",
                             "мчс"],
            "ОБЩЕСТВО": ["пенсия", "пособие", "жилье", "строительство", "жкх", "тарифы", "льготы", "социальный"],
            "ЗДОРОВЬЕ": ["врач", "медицина", "больница", "аптека", "вирус", "вакцина", "заболевание", "лечение"],
            "КУЛЬТУРА": ["выставка", "музей", "театр", "фестиваль", "концерт", "археолог", "находка", "памятник"],
            "КРИПТОВАЛЮТЫ": ["биткоин", "крипта", "майнинг", "токен", "blockchain", "криптовалют"]
        }

    @staticmethod
    def clean_text(text):
        if not text or not isinstance(text, str): return ""
        # 1. Отрезаем ссылки и соцсети в конце поста (обычно они начинаются с [Inst] или http)
        text = re.split(r'❤️|\[Inst\]|\[TikTok\]|http', text)[0]
        text = text.lower()
        text = re.sub(r'[^а-яёa-z\s]', ' ', text)
        return " ".join(text.split())

    def get_top_ngram_counts(self, texts, n=15):
        if texts is None or len(texts) == 0: return pd.DataFrame()
        try:
            cleaned_texts = texts.apply(self.clean_text)
            cleaned_texts = cleaned_texts[cleaned_texts.str.strip() != ""]
            if cleaned_texts.empty: return pd.DataFrame()
            vectorizer = CountVectorizer(stop_words=stop_words, ngram_range=(1, 2), max_features=n)
            X = vectorizer.fit_transform(cleaned_texts)
            df_counts = pd.DataFrame({'phrase': vectorizer.get_feature_names_out(), 'count': X.sum(axis=0).A1})
            return df_counts.sort_values(by='count', ascending=False)
        except:
            return pd.DataFrame()

    def _fast_categorize(self, text):
        text_lower = text.lower()
        for theme, words in self.fast_rules.items():
            if any(word in text_lower for word in words):
                return theme
        return None

    def cluster_messages(self, df):
        if df is None or df.empty: return df
        df_result = df.copy()
        df_result['cluster'] = "ОБЩЕЕ"

        for index, row in df_result.iterrows():
            raw_text = row.get('text', '')
            # Чистим текст ТОЛЬКО для анализа
            cleaned = self.clean_text(raw_text)

            if len(cleaned) < 10:
                continue

            # 1. Быстрый фильтр (теперь с погодой и обществом)
            theme = self._fast_categorize(cleaned)

            # 2. Нейросеть для остального
            if not theme and self.classifier:
                try:
                    # Подаем почищенный текст без ссылок
                    res = self.classifier(cleaned[:250], self.labels, multi_label=False)
                    theme = res['labels'][0].upper()
                except:
                    theme = "НОВОСТИ"
            elif not theme:
                theme = "НОВОСТИ"

            df_result.at[index, 'cluster'] = theme
        return df_result