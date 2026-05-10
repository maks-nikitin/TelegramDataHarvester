import sys
import os
import datetime
import asyncio
import streamlit as st
import pandas as pd
import plotly.express as px
import json

# Фикс путей
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(project_root)

from src.analytics.report_generator import PDFReport
from src.database.db_manager import DBManager
from src.analytics.processor import TextProcessor
from src.parser.collector import TelegramCollector

# Инициализация
db = DBManager()
collector = TelegramCollector()

config_path = "config/categories.json"
with open(config_path, 'r', encoding='utf-8') as f:
    CONFIG = json.load(f)

@st.cache_resource
def get_processor():
    return TextProcessor()


processor = get_processor()

# Настройки UI
st.set_page_config(page_title="TG Intellect Monitor", page_icon="🧠", layout="wide")

st.markdown("""
    <style>
    .post-card {
        padding: 20px;
        border-radius: 12px;
        margin-bottom: 15px;
        border: 1px solid rgba(128, 128, 128, 0.2);
        background: rgba(128, 128, 128, 0.03);
    }
    .badge {
        padding: 4px 12px;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: bold;
        color: white;
    }
    header {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)


def sync_data(username, start_date, end_date): # Добавили end_date
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        # Увеличили лимит до 500 для надежности
        raw = loop.run_until_complete(collector.fetch_messages(
            username,
            start_date=start_date,
            end_date=end_date,
            limit=500
        ))
        if raw:
            ids = db.get_existing_msg_ids(username)
            new_msgs = [m for m in raw if m.get('tg_msg_id') not in ids]
            if new_msgs:
                df_new = pd.DataFrame(new_msgs)
                df_new = processor.cluster_messages(df_new)
                df_new['date'] = df_new['date'].astype(str)
                db.save_messages(username, df_new.to_dict('records'))
                return len(new_msgs)
        return 0
    finally:
        loop.close()


# SIDEBAR
with st.sidebar:
    st.title("Intellect UI")
    target = st.text_input("Источник (@username)", placeholder="news_channel")

    st.write("---")
    st.write(" **Период анализа**")

    # Разделяем на две колонки, чтобы было компактно и открывалось вниз
    col1, col2 = st.columns(2)
    with col1:
        d_start = st.date_input("Начало", datetime.date.today() - datetime.timedelta(days=7))
    with col2:
        d_end = st.date_input("Конец", datetime.date.today())

    # Проверка логики дат
    if d_start > d_end:
        st.error("Ошибка: Дата начала позже даты конца")
    else:
        if st.button("Синхронизировать", use_container_width=True):
            if target:
                target_clean = target.split('/')[-1].replace('@', '')
                with st.spinner('Парсинг и ИИ анализ...'):
                    db.add_channel(target_clean)
                    count = sync_data(target_clean, d_start, d_end)
                    st.success(f"Готово! Добавлено: {count}")
                    st.rerun()
            else:
                st.warning("Введите @username")

    st.write("---")
    if st.button("🗑 Очистить базу", use_container_width=True):
        db.clear_all_data()
        st.rerun()

# MAIN
df_all = db.get_messages_df()

if df_all.empty:
    st.info("Система готова. Добавьте объект мониторинга в левой панели.")
else:
    ch_list = sorted(df_all['username'].unique())
    selected = st.selectbox("Текущий срез данных:", ["СВОДНЫЙ ОТЧЕТ"] + list(ch_list))
    df = df_all if selected == "СВОДНЫЙ ОТЧЕТ" else df_all[df_all['username'] == selected]

    # Аналитика
    st.markdown("### Аналитический дашборд")
    c1, c2 = st.columns(2)

    with c1:
        counts = df['cluster'].value_counts().reset_index()
        counts.columns = ['Тема', 'Кол-во']
        fig = px.pie(counts, values='Кол-во', names='Тема', hole=.5, title="Структура контента")
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        ng = processor.get_top_ngram_counts(df['text'])
        if not ng.empty:
            fig_bar = px.bar(ng, x='count', y='phrase', orientation='h', title="Ключевые слова и фразы")
            st.plotly_chart(fig_bar, use_container_width=True)

    st.divider()

    # Лента
    st.markdown(f"### Интеллектуальная лента: {selected}")

    c_exp1, c_exp2 = st.columns(2)

    with c_exp1:
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(" Экспорт в CSV", csv, f"report_{selected}.csv", "text/csv", use_container_width=True)

    with c_exp2:
        if st.button(" Сформировать PDF-отчет", use_container_width=True):
            # 1. Сначала получаем ключевые слова для текущего среза
            kw_df = processor.get_top_ngram_counts(df['text'])

            # 2. Генерируем PDF
            with st.spinner("Создание документа..."):
                report_gen = PDFReport()
                pdf_bytes = report_gen.generate(df, kw_df, selected)

                st.download_button(
                    label=" Скачать PDF",
                    data=bytes(pdf_bytes),
                    file_name=f"report_{selected}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

    for _, row in df.sort_values(by='date', ascending=False).iterrows():
        bg_color = CONFIG['categories'].get(row['cluster'], "#95a5a6")

        st.markdown(f"""
            <div class="post-card">
                <div style="display: flex; justify-content: space-between;">
                    <span class="badge" style="background-color: {bg_color};">{row['cluster']}</span>
                    <span style="opacity: 0.5; font-size: 0.8rem;">{row['date']}</span>
                </div>
                <div style="margin-top: 12px; font-size: 1.05rem; line-height: 1.6;">{row['text']}</div>
                <div style="margin-top: 15px; display: flex; gap: 20px; font-size: 0.85rem; opacity: 0.6;">
                    <span>👁 {row['views']}</span>
                    <span>🔄 {row['forwards']}</span>
                    <span>❤️ {row['reactions']}</span>
                    <span style="color: #0088CC;">@{row['username']}</span>
                </div>
            </div>
        """, unsafe_allow_html=True)