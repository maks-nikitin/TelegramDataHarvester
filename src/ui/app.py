import sys
import os
import datetime
import asyncio

# Исправление путей
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(project_root)

import streamlit as st
import pandas as pd
from src.database.db_manager import DBManager
from src.analytics.processor import TextProcessor
from src.parser.collector import TelegramCollector  # Импортируем наш парсер

# Инициализация
db = DBManager()
processor = TextProcessor()
collector = TelegramCollector()

st.set_page_config(page_title="TG Analyzer", page_icon="📊", layout="wide")


# Функция для запуска асинхронного парсера внутри Streamlit
def run_parser(username, limit):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    data = loop.run_until_complete(collector.fetch_messages(username, limit))
    return data


st.title("📊 Реальный сбор и анализ Telegram")

# --- SIDEBAR ---
st.sidebar.header("🎛 Управление")

channel_to_parse = st.sidebar.text_input("Username канала для парсинга", placeholder="@news")
count = st.sidebar.slider("Сколько сообщений собрать?", 10, 200, 50)

if st.sidebar.button("🚀 Запустить сбор"):
    if channel_to_parse:
        with st.spinner(f'Связываюсь с Telegram и собираю данные из {channel_to_parse}...'):
            # 1. Добавляем канал в базу
            db.add_channel(channel_to_parse)
            # 2. Собираем данные через парсер
            real_data = run_parser(channel_to_parse, count)

            if real_data:
                # 3. Сохраняем в базу
                db.save_messages(channel_to_parse, real_data)
                st.sidebar.success(f"Готово! Собрано {len(real_data)} постов.")
                st.rerun()
            else:
                st.sidebar.error("Не удалось собрать данные. Проверьте username.")
    else:
        st.sidebar.warning("Введите @username!")

# Кнопка очистки базы (чтобы начать с чистого листа)
if st.sidebar.button("🗑 Очистить базу данных"):
    db.clear_all_data()  # Используем новый метод вместо os.remove
    st.sidebar.success("Данные успешно удалены!")
    st.rerun()

# --- ОСНОВНОЙ ЭКРАН ---
df = db.get_messages_df()

if df.empty:
    st.info("👋 База данных пока пуста. Введите @username в меню слева и нажмите 'Запустить сбор'.")
else:
    # Метрики
    m1, m2, m3 = st.columns(3)
    m1.metric("Сообщений в базе", len(df))
    m2.metric("Общий охват", f"{df['views'].sum():,}")
    m3.metric("Каналов проанализировано", len(df['username'].unique()))

    st.divider()

    # Аналитика
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("🔑 Ключевые слова")
        keywords = processor.get_top_keywords(df['text'], n=10)
        st.write(", ".join(keywords) if keywords else "Анализ слов недоступен")

    with col_right:
        st.subheader("📈 Статистика по каналам")
        st.bar_chart(df['username'].value_counts())

    st.subheader("🤖 Темы сообщений")
    df_clustered = processor.cluster_messages(df)
    st.dataframe(df_clustered[['username', 'date', 'text', 'views', 'cluster']], width=1200)  # исправили параметр width

    # Кнопка скачивания
    csv = df_clustered.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Скачать отчет (CSV)", csv, "tg_report.csv", "text/csv")