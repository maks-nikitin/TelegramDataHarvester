import time
import asyncio
import traceback
import sys
import os
import datetime
import asyncio
import streamlit as st
import pandas as pd
import plotly.express as px
import json


# --- НАСТРОЙКА ПУТЕЙ ---
# Добавляем корень проекта в системные пути Python, чтобы модули из папки src
# могли "видеть" друг друга независимо от того, откуда запущен скрипт.
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(project_root)

# Импортируем наши собственные модули
from src.database.db_manager import DBManager
from src.analytics.processor import TextProcessor
from src.parser.collector import TelegramCollector
from src.analytics.report_generator import PDFReport

# --- ИНИЦИАЛИЗАЦИЯ ОБЪЕКТОВ ---
db = DBManager()
collector = TelegramCollector()


# Используем декоратор @st.cache_resource, чтобы тяжелая нейросеть загрузилась
# в память только один раз при старте, а не при каждом обновлении страницы.
@st.cache_resource
def get_processor():
    return TextProcessor()


processor = get_processor()

# Загружаем конфигурацию категорий для синхронизации цветов в UI
config_path = os.path.join(project_root, "config/categories.json")
with open(config_path, 'r', encoding='utf-8') as f:
    CONFIG = json.load(f)

# --- НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="TG Intellect Monitor", page_icon="🧠", layout="wide")

# Внедрение кастомного CSS для создания красивых карточек постов и бейджей
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
    header {visibility: hidden;} /* Убираем лишние элементы Streamlit */
    </style>
""", unsafe_allow_html=True)


# --- ЛОГИКА СИНХРОНИЗАЦИИ ---
def sync_data(username, start_date, end_date):
    print(f"\n--- [DEBUG START] Попытка синхронизации @{username} ---")

    try:
        global_start = time.time()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # 1. Парсинг
        print(f"DEBUG: Вызов collector.fetch_messages с {start_date} по {end_date}...")
        raw = loop.run_until_complete(collector.fetch_messages(
            username, start_date=start_date, end_date=end_date, limit=500
        ))

        if raw is None:
            print("DEBUG: Collector вернул None! Проверь подключение к Telegram.")
            return 0

        print(f"DEBUG: Собрано сообщений из API: {len(raw)}")

        if not raw:
            print("DEBUG: За указанный период постов нет.")
            return 0

        # 2. Фильтрация дубликатов
        print("DEBUG: Проверка существующих ID в базе...")
        ids = db.get_existing_msg_ids(username)
        new_msgs = [m for m in raw if m.get('tg_msg_id') not in ids]
        print(f"DEBUG: Новых (которых нет в базе): {len(new_msgs)}")

        if not new_msgs:
            print("DEBUG: Синхронизация не требуется, всё уже в базе.")
            return 0

        # 3. Работа ИИ
        print("DEBUG: Отправка в TextProcessor...")
        df_new = pd.DataFrame(new_msgs)
        df_new = processor.cluster_messages(df_new)

        # 4. Сохранение
        print("DEBUG: Сохранение в БД...")
        df_new['date'] = df_new['date'].astype(str)
        db.save_messages(username, df_new.to_dict('records'))

        total_time = time.time() - global_start
        print(f"--- [DEBUG SUCCESS] Завершено за {total_time:.2f} сек. Добавлено: {len(new_msgs)} ---")
        return len(new_msgs)

    except Exception as e:
        print("\n❌❌❌ [CRITICAL ERROR IN SYNC_DATA] ❌❌❌")
        # Эта команда выведет в консоль ПОЛНЫЙ путь ошибки (на какой строке и почему упало)
        traceback.print_exc()
        print("-------------------------------------------\n")
        return -1
    finally:
        loop.close()


# --- БОКОВАЯ ПАНЕЛЬ (SIDEBAR) ---
with st.sidebar:
    st.title("Intellect UI")
    target = st.text_input("Источник (@username)", placeholder="news_channel")

    st.write("---")
    st.write(" **Период анализа**")
    # Раздельный ввод дат для стабильного отображения в узком сайдбаре
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        d_start = st.date_input("Начало", datetime.date.today() - datetime.timedelta(days=7))
    with col_d2:
        d_end = st.date_input("Конец", datetime.date.today())

    # Логика кнопки синхронизации
    if d_start > d_end:
        st.error("Дата начала позже даты конца")
    else:
        if st.button("Синхронизировать", use_container_width=True):
            if target:
                # Очищаем юзернейм от лишних символов (@ или ссылки)
                clean_target = target.split('/')[-1].replace('@', '')
                with st.spinner('Парсинг и ИИ анализ...'):
                    db.add_channel(clean_target)
                    count = sync_data(clean_target, d_start, d_end)
                    st.success(f"Добавлено: {count}")
                    st.rerun()  # Обновляем страницу, чтобы увидеть данные

    st.write("---")
    if st.button("🗑 Очистить базу", use_container_width=True):
        db.clear_all_data()
        st.rerun()

# --- ОСНОВНАЯ ОБЛАСТЬ ---
df_all = db.get_messages_df()

if df_all.empty:
    st.info("Система готова. Введите название канала в левой панели для начала анализа.")
else:
    # Выбор конкретного канала для фильтрации данных
    channels = sorted(df_all['username'].unique())
    selected = st.selectbox("Текущий срез данных:", ["СВОДНЫЙ ОТЧЕТ"] + list(channels))
    df = df_all if selected == "СВОДНЫЙ ОТЧЕТ" else df_all[df_all['username'] == selected]

    # --- ВИЗУАЛИЗАЦИЯ (ДАШБОРД) ---
    st.markdown("### Аналитический дашборд")
    c1, c2 = st.columns(2)

    with c1:
        # Круговая диаграмма распределения постов по темам
        theme_counts = df['cluster'].value_counts().reset_index()
        theme_counts.columns = ['Тема', 'Кол-во']
        fig = px.pie(theme_counts, values='Кол-во', names='Тема', hole=.5, title="Структура контента")
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        # Столбчатая диаграмма частотности ключевых фраз (NLP анализ)
        kw_df = processor.get_top_ngram_counts(df['text'])
        if not kw_df.empty:
            fig_bar = px.bar(kw_df.head(15), x='count', y='phrase', orientation='h', title="Ключевые слова и фразы")
            fig_bar.update_layout(yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig_bar, use_container_width=True)

    st.divider()

    # --- ЭКСПОРТ И ЛЕНТА ---
    st.markdown(f"### Интеллектуальная лента: {selected}")

    # Кнопки выгрузки результатов
    exp_col1, exp_col2 = st.columns(2)
    with exp_col1:
        csv_data = df.to_csv(index=False).encode('utf-8')
        st.download_button(" Экспорт в CSV", csv_data, f"report_{selected}.csv", "text/csv", use_container_width=True)

    with exp_col2:
        if st.button(" Сформировать PDF-отчет", use_container_width=True):
            with st.spinner("Генерация документа..."):
                # Собираем PDF, передавая данные и ключевые слова
                report_gen = PDFReport()
                pdf_bytes = report_gen.generate(df, kw_df, selected)
                st.download_button(" Скачать PDF", data=bytes(pdf_bytes), file_name=f"report_{selected}.pdf",
                                   use_container_width=True)

    # Отрисовка ленты сообщений в виде карточек
    for _, row in df.sort_values(by='date', ascending=False).iterrows():
        # Динамически подбираем цвет бейджа из конфига
        cat_color = CONFIG['categories'].get(row['cluster'], "#95a5a6")

        st.markdown(f"""
            <div class="post-card">
                <div style="display: flex; justify-content: space-between;">
                    <span class="badge" style="background-color: {cat_color};">{row['cluster']}</span>
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