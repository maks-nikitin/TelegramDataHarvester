import sys
import os
import datetime
import asyncio
import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh

# --- ИСПРАВЛЕНИЕ ПУТЕЙ ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.database.db_manager import DBManager
from src.analytics.processor import TextProcessor
from src.parser.collector import TelegramCollector

db = DBManager()
collector = TelegramCollector()


@st.cache_resource
def get_processor():
    return TextProcessor()


processor = get_processor()


# Функция синхронизации с учетом даты
def sync_data(username, start_date):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        # Собираем данные за период
        raw_data = loop.run_until_complete(collector.fetch_messages(username, start_date=start_date, limit=200))
        if raw_data:
            existing_ids = db.get_existing_msg_ids(username)
            new_messages = [m for m in raw_data if m.get('tg_msg_id') not in existing_ids]

            if new_messages:
                df_new = pd.DataFrame(new_messages)
                df_new = processor.cluster_messages(df_new)
                df_new['date'] = df_new['date'].astype(str)
                db.save_messages(username, df_new.to_dict('records'))
                return len(new_messages)
        return 0
    finally:
        loop.close()


# --- ИНТЕРФЕЙС ---
st.set_page_config(page_title="TG Analyzer Pro", layout="wide")
st_autorefresh(interval=120000, key="auto")  # Каждые 2 минуты для "автоматизма"

# Дизайн
st.markdown("""
    <style>
    .stApp { background-color: #0F1116; }
    [data-testid="metric-container"] { background-color: #161A23; border: 1px solid #2D323E; padding: 10px; border-radius: 8px; }
    </style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.title("📡 Сбор метрик")
    target = st.text_input("Username канала/группы", placeholder="grodnonewsby")

    # ТРЕБОВАНИЕ ТЗ: Выбранный период
    st.subheader("Выбор периода")
    lookback_date = st.date_input("Собрать данные начиная с:", datetime.date.today() - datetime.timedelta(days=7))

    if st.button("🚀 Запустить сбор"):
        if target:
            # Очистка юзернейма
            target = target.split('/')[-1].replace('@', '')
            with st.spinner('Автоматический сбор и анализ...'):
                db.add_channel(target)
                added = sync_data(target, lookback_date)
                st.success(f"Завершено. Новых сообщений: {added}")
                st.rerun()

# --- ОСНОВНОЙ ЭКРАН ---
df_all = db.get_messages_df()

if df_all.empty:
    st.info("👋 Система готова. Введите данные канала и период в левой панели.")
else:
    channels = sorted(df_all['username'].unique())
    selected = st.selectbox("📂 Объект анализа:", ["ВСЕ КАНАЛЫ"] + list(channels))

    df = df_all if selected == "ВСЕ КАНАЛЫ" else df_all[df_all['username'] == selected]

    # Метрики за ВЕСЬ период в базе
    m = st.columns(4)
    m[0].metric("Всего сообщений", len(df))
    m[1].metric("Общие просмотры", f"{df['views'].sum():,}")
    m[2].metric("Сумма реакций", f"{df['reactions'].sum():,}")
    m[3].metric("Пересылки", f"{df['forwards'].sum():,}")

    st.divider()

    t1, t2, t3 = st.tabs(["📊 Тематика", "🔑 Ключевые слова", "📜 Лента"])

    with t1:
        st.subheader("Кластеризация сообщений по темам")
        if 'cluster' in df.columns:
            st.bar_chart(df['cluster'].value_counts(), color="#0088CC")

    with t2:
        st.subheader("Топ-15 ключевых фраз (n-граммы)")
        ng = processor.get_top_ngram_counts(df['text'])
        if not ng.empty:
            st.bar_chart(ng, x='phrase', y='count', color="#5865F2")

    with t3:
        st.subheader("Собранные сообщения и метрики")
        # Показываем таблицу с просмотры, репосты (forwards), реакции
        st.dataframe(
            df[['date', 'cluster', 'text', 'views', 'forwards', 'reactions']].sort_values(by='date', ascending=False),
            use_container_width=True, hide_index=True
        )
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Экспорт отчета (CSV)", csv, "report.csv")