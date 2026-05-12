import sys
import os
import datetime
import asyncio
import streamlit as st
import pandas as pd
import plotly.express as px
import json
import time
import traceback

# --- НАСТРОЙКА ПУТЕЙ (PYTHON PATH) ---
# Чтобы модули из папки src могли импортировать друг друга,
# мы добавляем корень проекта в системные пути поиска Python.
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(project_root)

# Импортируем наши ранее созданные модули
from src.database.db_manager import DBManager
from src.analytics.processor import TextProcessor
from src.parser.collector import TelegramCollector
from src.analytics.report_generator import PDFReport

# --- ИНИЦИАЛИЗАЦИЯ ОБЪЕКТОВ ---
db = DBManager()
collector = TelegramCollector()


# Декоратор @st.cache_resource заставляет Streamlit загрузить нейросеть
# в память только ОДИН раз. При обновлении страницы модель не будет
# загружаться заново, что экономит время и ресурсы.
@st.cache_resource
def get_processor():
    return TextProcessor()


processor = get_processor()

# Загружаем JSON-конфиг с категориями и их цветами для UI
config_path = os.path.join(project_root, "config/categories.json")
with open(config_path, 'r', encoding='utf-8') as f:
    CONFIG = json.load(f)

# --- ГЛОБАЛЬНЫЕ НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="TG Intellect Monitor", page_icon="🧠", layout="wide")

# Внедрение кастомного CSS для оформления карточек сообщений (эффект стекла)
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
    </style>
""", unsafe_allow_html=True)


# --- ЛОГИКА СИНХРОНИЗАЦИИ (ЯДРО ПРОЦЕССА) ---
def sync_data(username, start_date, end_date):
    """
    Функция-мостик: запускает асинхронный сбор данных,
    прогоняет их через ИИ и сохраняет в базу данных.
    """
    print(f"\n--- [DEBUG START] Синхронизация @{username} ---")
    try:
        global_start = time.time()

        # Создаем цикл событий (Event Loop) для выполнения асинхронного кода Telethon
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # 1. ШАГ: СБОР ДАННЫХ ИЗ TELEGRAM
        # Вызываем метод парсера. Ограничение 500 постов для стабильности.
        raw = loop.run_until_complete(collector.fetch_messages(
            username, start_date=start_date, end_date=end_date, limit=500
        ))

        if not raw:
            print("DEBUG: За выбранный период сообщений не найдено.")
            return 0

        # 2. ШАГ: ФИЛЬТРАЦИЯ ДУБЛИКАТОВ
        # Спрашиваем базу, какие посты мы уже знаем, и оставляем только "свежие"
        ids = db.get_existing_msg_ids(username)
        new_msgs = [m for m in raw if m.get('tg_msg_id') not in ids]

        if not new_msgs:
            print("DEBUG: Всё уже есть в базе, анализ не требуется.")
            return 0

        # 3. ШАГ: НЕЙРОСЕТЕВОЙ АНАЛИЗ (ИИ)
        # Отправляем только новые посты на классификацию тем
        df_new = pd.DataFrame(new_msgs)
        df_new = processor.cluster_messages(df_new)

        # 4. ШАГ: СОХРАНЕНИЕ В БАЗУ ДАННЫХ
        # Приводим дату к строке для корректного хранения в SQLite
        df_new['date'] = df_new['date'].astype(str)
        db.save_messages(username, df_new.to_dict('records'))

        total_time = time.time() - global_start
        print(f"--- [DEBUG SUCCESS] Завершено за {total_time:.2f} сек. ---")
        return len(new_msgs)

    except Exception as e:
        # Если что-то пошло не так, выводим полную ошибку в консоль и на экран
        print("\n [CRITICAL ERROR]")
        traceback.print_exc()
        st.error(f"Ошибка: {e}")
        return -1
    finally:
        loop.close()


# --- БОКОВАЯ ПАНЕЛЬ (SIDEBAR) ---
with st.sidebar:
    st.title("Intellect UI")
    # Поле ввода юзернейма канала
    target = st.text_input("Источник (@username)", placeholder="news_channel")

    st.write("---")
    st.write(" **Период анализа**")

    # Раздельный ввод дат (начало и конец периода)
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        d_start = st.date_input("Начало", datetime.date.today() - datetime.timedelta(days=7))
    with col_d2:
        d_end = st.date_input("Конец", datetime.date.today())

    # Проверка логики дат перед запуском
    if d_start > d_end:
        st.error("Ошибка: Начало позже Конца!")
    else:
        if st.button("Синхронизировать", use_container_width=True):
            if target:
                # Очистка юзернейма от символа @ и ссылок
                clean_target = target.split('/')[-1].replace('@', '')
                with st.spinner('Парсинг и ИИ анализ...'):
                    db.add_channel(clean_target)
                    count = sync_data(clean_target, d_start, d_end)
                    if count >= 0:
                        st.success(f"Готово! Добавлено: {count}")
                        st.rerun()  # Перезагрузка страницы для отображения данных
            else:
                st.warning("Введите @username")

    st.write("---")
    # Кнопка полной очистки базы данных
    if st.button("🗑 Очистить базу", use_container_width=True):
        db.clear_all_data()
        st.rerun()

# --- ОСНОВНАЯ ОБЛАСТЬ (MAIN AREA) ---
# Получаем все данные из SQLite для отображения
df_all = db.get_messages_df()

if df_all.empty:
    st.info(" Система готова. Введите название канала в левой панели, чтобы начать сбор данных.")
else:
    # Селектор для выбора конкретного канала или сводного отчета по всем
    channels = sorted(df_all['username'].unique())
    selected = st.selectbox("Текущий срез данных:", ["СВОДНЫЙ ОТЧЕТ"] + list(channels))

    # Фильтруем данные согласно выбору пользователя
    df = df_all if selected == "СВОДНЫЙ ОТЧЕТ" else df_all[df_all['username'] == selected]

    # --- ВИЗУАЛИЗАЦИЯ (ДАШБОРД) ---
    st.markdown("### Аналитический дашборд")
    c1, c2 = st.columns(2)

    with c1:
        # Круговая диаграмма (Pie Chart) распределения постов по темам
        theme_counts = df['cluster'].value_counts().reset_index()
        theme_counts.columns = ['Тема', 'Кол-во']
        fig = px.pie(theme_counts, values='Кол-во', names='Тема', hole=.5, title="Структура контента")
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        # Горизонтальный график (Bar Chart) ТОП-15 ключевых слов/фраз
        kw_df = processor.get_top_ngram_counts(df['text'])
        if not kw_df.empty:
            fig_bar = px.bar(kw_df.head(15), x='count', y='phrase', orientation='h', title="Ключевые фразы")
            fig_bar.update_layout(yaxis={'categoryorder': 'total ascending'})  # Сортировка по убыванию
            st.plotly_chart(fig_bar, use_container_width=True)

    st.divider()

    # --- ЛЕНТА И ЭКСПОРТ ---
    st.markdown(f"### Интеллектуальная лента: {selected}")

    # Кнопки для выгрузки результатов анализа
    exp1, exp2 = st.columns(2)
    with exp1:
        # Экспорт текущей таблицы в CSV
        csv_data = df.to_csv(index=False).encode('utf-8')
        st.download_button(" Экспорт в CSV", csv_data, f"report_{selected}.csv", "text/csv", use_container_width=True)

    with exp2:
        # Кнопка генерации полноценного PDF-отчета
        if st.button(" Сформировать PDF-отчет", use_container_width=True):
            with st.spinner("Создание документа..."):
                report_gen = PDFReport()
                # Передаем в генератор сами данные и таблицу ключевых слов
                pdf_bytes = report_gen.generate(df, kw_df, selected)
                st.download_button("⬇ Скачать PDF", data=bytes(pdf_bytes), file_name=f"report_{selected}.pdf",
                                   use_container_width=True)

    # ОТРИСОВКА КАРТОЧЕК ПОСТОВ
    # Сортируем от новых к старым
    for _, row in df.sort_values(by='date', ascending=False).iterrows():
        # Подбираем цвет бейджа (категории) из нашего конфига JSON
        cat_color = CONFIG['categories'].get(row['cluster'], "#95a5a6")

        # Вывод поста в виде красивого блока через HTML-инъекцию
        st.markdown(f"""
            <div class="post-card">
                <div style="display: flex; justify-content: space-between;">
                    <span class="badge" style="background-color: {cat_color};">{row['cluster']}</span>
                    <span style="opacity: 0.5; font-size: 0.8rem;">{row['date']}</span>
                </div>
                <div style="margin-top: 12px; font-size: 1.05rem; line-height: 1.6;">{row['text']}</div>
                <div style="margin-top: 15px; display: flex; gap: 20px; font-size: 0.85rem; opacity: 0.6;">
                    <span>👁 {int(row['views'])}</span>
                    <span>🔄 {int(row['forwards'])}</span>
                    <span>❤️ {int(row['reactions'])}</span>
                    <span style="color: #0088CC;">@{row['username']}</span>
                </div>
            </div>
        """, unsafe_allow_html=True)