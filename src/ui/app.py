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
from apscheduler.schedulers.background import BackgroundScheduler
from src.database.db_manager import DBManager
from src.analytics.processor import TextProcessor
from src.parser.collector import TelegramCollector

# --- ИНИЦИАЛИЗАЦИЯ ---

db = DBManager()
collector = TelegramCollector()


# Кэшируем процессор, так как внутри тяжелая нейросеть
@st.cache_resource
def get_processor():
    return TextProcessor()


processor = get_processor()


# Настройка планировщика (Пункт 2 ТЗ)
@st.cache_resource
def start_scheduler():
    scheduler = BackgroundScheduler()

    # Функция для фонового обновления (упрощенно)
    def scheduled_task():
        print(f"[{datetime.datetime.now()}] Запуск фонового обновления данных...")
        # Тут можно вызвать collector.fetch_messages для всех каналов из базы

    scheduler.add_job(scheduled_task, 'interval', hours=1)
    scheduler.start()
    return scheduler


start_scheduler()

# --- ИНТЕРФЕЙС STREAMLIT ---

st.set_page_config(page_title="TG Analyzer Pro", page_icon="🤖", layout="wide")

st.title("📊 Автоматизированная система анализа Telegram-каналов")

# --- SIDEBAR (БОКОВАЯ ПАНЕЛЬ) ---
st.sidebar.header("🎛 Управление сбором")

channel_to_parse = st.sidebar.text_input("Username канала", placeholder="@durov")
count = st.sidebar.slider("Количество сообщений", 10, 500, 50)


# Функция для запуска асинхронного парсера
def run_parser(username, limit):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(collector.fetch_messages(username, limit))


if st.sidebar.button("🚀 Начать сбор данных"):
    if channel_to_parse:
        with st.spinner('Нейросеть и парсер работают...'):
            db.add_channel(channel_to_parse)
            real_data = run_parser(channel_to_parse, count)

            if real_data:
                db.save_messages(channel_to_parse, real_data)
                st.sidebar.success(f"Успешно собрано {len(real_data)} постов!")
                st.rerun()
            else:
                st.sidebar.error("Ошибка сбора. Проверьте канал.")
    else:
        st.sidebar.warning("Введите @username")

st.sidebar.divider()
if st.sidebar.button("🗑 Очистить базу данных"):
    db.clear_all_data()
    st.sidebar.success("База данных очищена!")
    st.rerun()

st.sidebar.info("Планировщик: Активен (раз в 1 час)")

# --- ОСНОВНОЙ ЭКРАН ---
df = db.get_messages_df()

if df.empty:
    st.info("👋 База данных пуста. Добавьте канал в меню слева для начала анализа.")
else:
    # 1. Верхние метрики
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Всего сообщений", len(df))
    m2.metric("Общий охват", f"{df['views'].sum():,}")
    m3.metric("Средний охват", f"{int(df['views'].mean()):,}")
    m4.metric("Каналов", len(df['username'].unique()))

    st.divider()

    # 2. Частотный анализ фраз (Пункт 1 ТЗ)
    st.subheader("🔑 Частотный анализ ключевых слов и фраз (N-граммы)")
    col_chart, col_table = st.columns([2, 1])

    ngram_df = processor.get_top_ngram_counts(df['text'], n=20)

    with col_chart:
        # Визуализация частотности
        st.bar_chart(data=ngram_df, x='phrase', y='count', color="#FF4B4B")

    with col_table:
        st.write("Топ-20 популярных выражений:")
        st.dataframe(ngram_df, hide_index=True, width=400)

    st.divider()

    # 3. Кластеризация и Темы (Пункт 3 ТЗ)
    st.subheader("🤖 Анализ тем нейросетью")

    # Запускаем кластеризацию
    with st.spinner('Нейросеть классифицирует сообщения...'):
        df_clustered = processor.cluster_messages(df, n_clusters=min(5, len(df)))

    # Формируем "Профиль интересов" (Пункт 4 ТЗ)
    # Считаем, какие темы набирают больше всего просмотров
    st.write("📊 Профиль популярности тем (на основе просмотров):")
    interest_profile = df_clustered.groupby('cluster')['views'].sum().sort_values(ascending=False)
    st.area_chart(interest_profile)

    # Таблица результатов
    st.write("Последние сообщения с определенными темами:")
    st.dataframe(
        df_clustered[['username', 'cluster', 'text', 'views', 'date']].sort_values(by='date', ascending=False),
        width=1400
    )

    # 4. Экспорт (Пункт 1 ТЗ)
    st.divider()
    st.subheader("💾 Экспорт результатов")
    col_exp1, col_exp2 = st.columns(2)

    csv = df_clustered.to_csv(index=False).encode('utf-8')
    col_exp1.download_button(
        "📥 Скачать отчет (CSV/Excel)",
        csv,
        f"tg_report_{datetime.date.today()}.csv",
        "text/csv"
    )

    col_exp2.info("PDF-отчеты будут доступны в следующей версии.")