import sys
import os
import datetime
import asyncio
import streamlit as st
import pandas as pd

# Исправление путей
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(src_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.database.db_manager import DBManager
from src.analytics.processor import TextProcessor
from src.parser.collector import TelegramCollector

# Инициализация
db = DBManager()
collector = TelegramCollector()


@st.cache_resource
def get_processor():
    return TextProcessor()


processor = get_processor()

# Настройка страницы
st.set_page_config(page_title="TG Analyzer Pro", page_icon="🤖", layout="wide")
st.title(" Автоматизация анализа Telegram-каналов")

# SideBar
st.sidebar.header("🎛 Сбор данных")
new_ch = st.sidebar.text_input("Введите @username", placeholder="@durov")
msg_count = st.sidebar.slider("Сколько сообщений?", 10, 500, 10)


def run_parser_sync(username, limit):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(collector.fetch_messages(username, limit))
    finally:
        loop.close()


if st.sidebar.button(" Собрать / Обновить"):
    if new_ch:
        with st.spinner('Парсинг и работа ИИ...'):
            db.add_channel(new_ch)
            raw_data = run_parser_sync(new_ch, msg_count)
            if raw_data:
                existing_ids = db.get_existing_msg_ids(new_ch)
                new_messages = [m for m in raw_data if m.get('tg_msg_id') not in existing_ids]

                if new_messages:
                    df_new = pd.DataFrame(new_messages)
                    df_new = processor.cluster_messages(df_new)
                    df_new['date'] = df_new['date'].astype(str)
                    db.save_messages(new_ch, df_new.to_dict('records'))
                    st.sidebar.success(f"Добавлено {len(new_messages)} постов!")
                else:
                    st.sidebar.success("Новых постов нет.")
                st.rerun()
    else:
        st.sidebar.warning("Введите юзернейм!")

if st.sidebar.button("🗑 Очистить всю базу"):
    db.clear_all_data()
    st.rerun()

# --- ГЛАВНЫЙ ЭКРАН ---
df_all = db.get_messages_df()

if df_all.empty:
    st.info(" Добавьте первый канал слева.")
else:
    ch_list = sorted(df_all['username'].unique())
    selected_page = st.selectbox(" Выберите канал:", ["ОБЩАЯ СТАТИСТИКА"] + list(ch_list))

    df = df_all if selected_page == "ОБЩАЯ СТАТИСТИКА" else df_all[df_all['username'] == selected_page]

    # Кнопка скачивания CSV вверху справа
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button(" Скачать текущие данные (CSV)", csv, f"report_{selected_page}.csv", "text/csv")

    # Метрики
    m = st.columns(4)
    m[0].metric("Постов", len(df))
    m[1].metric("Просмотров", f"{df['views'].sum():,}")
    m[2].metric("Реакций", f"{df['reactions'].sum():,}")
    m[3].metric("Пересылок", f"{df['forwards'].sum():,}")

    st.divider()

    # N-граммы
    st.subheader(" Популярные выражения")
    ng_df = processor.get_top_ngram_counts(df['text'])
    if not ng_df.empty:
        st.bar_chart(ng_df, x='phrase', y='count', color="#FF4B4B")

    st.divider()

    # Кластеры
    st.subheader(" Тематический анализ (ИИ)")
    c1, c2 = st.columns([1, 2])
    with c1:
        st.write(" Темы канала:")
        st.bar_chart(df['cluster'].value_counts())
    with c2:
        st.write("Последние классифицированные сообщения:")
        st.dataframe(
            df[['cluster', 'text', 'views', 'reactions', 'date']].sort_values(by='date', ascending=False).head(20),
            hide_index=True, use_container_width=True
        )

    with st.expander(" Таблица всех данных"):
        st.dataframe(df.sort_values(by='date', ascending=False), use_container_width=True)