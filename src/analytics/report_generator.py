from fpdf import FPDF
import datetime
import os
import re


class PDFReport:
    """
    Класс для автоматической генерации PDF-отчетов.
    Отвечает за верстку документа, поддержку кириллицы и очистку текста для печати.
    """

    def __init__(self):
        # Инициализируем библиотеку FPDF
        self.pdf = FPDF()
        # Настраиваем автоматический перенос на новую страницу при достижении нижнего поля (20 мм)
        self.pdf.set_auto_page_break(auto=True, margin=20)
        # Добавляем первую страницу
        self.pdf.add_page()

        # РАБОТА СО ШРИФТАМИ (Важно для поддержки русского языка)
        # Обычные PDF не знают кириллицу. Мы ищем в системе шрифт Arial
        # или используем DejaVu, чтобы вместо букв не было «кракозябр».
        font_path = "C:\\Windows\\Fonts\\arial.ttf"
        if os.path.exists(font_path):
            self.pdf.add_font("Arial", "", font_path)
            self.pdf.add_font("Arial", "B", "C:\\Windows\\Fonts\\arialbd.ttf")  # Жирный вариант
            self.font_name = "Arial"
        else:
            # Если Arial в системе нет, загружаем встроенный в библиотеку DejaVu
            self.pdf.add_font("DejaVu", "", "https://github.com/reingart/pyfpdf/raw/master/fpdf/font/DejaVuSans.ttf")
            self.pdf.add_font("DejaVu", "B",
                              "https://github.com/reingart/pyfpdf/raw/master/fpdf/font/DejaVuSans-Bold.ttf")
            self.font_name = "DejaVu"

    def clean_text_for_pdf(self, text):
        """
        Агрессивная очистка текста специально для PDF.
        Удаляет ссылки и Markdown, которые ломают ширину страницы и вылетают за края.
        """
        if not text: return ""
        # 1. Удаляем все ссылки (http, https, t.me)
        text = re.sub(r'https?://\S+', '', text)
        text = re.sub(r't\.me/\S+', '', text)
        # 2. Удаляем Markdown-разметку ссылок [текст](ссылка) -> оставляем только 'текст'
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        # 3. Удаляем спецсимволы форматирования (*, _, `)
        text = text.replace('*', '').replace('_', '').replace('`', '')
        # 4. Оставляем только базовые символы (буквы, цифры, пунктуацию),
        # чтобы 'невидимые' символы Telegram не сбивали расчет ширины строки.
        text = re.sub(r'[^\w\s\.\,\!\?\-\:\(\)\"\']', ' ', text)
        return " ".join(text.split())

    def generate(self, df, kw_df, channel_name):
        """
        Основной метод сборки PDF-документа.
        df: таблица сообщений из БД
        kw_df: таблица ключевых слов из процессора
        channel_name: название канала для заголовка
        """
        # --- 1. ТИТУЛЬНЫЙ ЛИСТ ---
        self.pdf.set_font(self.font_name, 'B', 16)
        self.pdf.cell(0, 10, txt=f"ОТЧЕТ: {channel_name.upper()}", ln=True, align='C')

        self.pdf.set_font(self.font_name, size=10)
        self.pdf.cell(0, 8, txt=f"Дата создания: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}", ln=True,
                      align='C')
        self.pdf.ln(10)

        # --- 2. СВОДНЫЕ ПОКАЗАТЕЛИ ---
        self.pdf.set_font(self.font_name, 'B', 12)
        self.pdf.set_fill_color(200, 220, 255)  # Светло-голубой фон для заголовка секции
        self.pdf.cell(0, 10, txt=" 1. СВОДНЫЕ ПОКАЗАТЕЛИ", ln=True, fill=True)

        self.pdf.set_font(self.font_name, size=10)
        self.pdf.ln(2)
        self.pdf.cell(0, 7, txt=f"Проанализировано сообщений: {len(df)}", ln=True)
        self.pdf.cell(0, 7, txt=f"Общее кол-во просмотров: {int(df['views'].sum())}", ln=True)
        self.pdf.cell(0, 7, txt=f"Общее кол-во реакций: {int(df['reactions'].sum())}", ln=True)
        self.pdf.ln(10)

        # --- 3. КЛЮЧЕВЫЕ СЛОВА ---
        self.pdf.set_font(self.font_name, 'B', 12)
        self.pdf.cell(0, 10, txt=" 2. КЛЮЧЕВЫЕ СЛОВА (ТОП-15)", ln=True, fill=True)

        self.pdf.set_font(self.font_name, size=10)
        self.pdf.ln(2)
        if kw_df is not None and not kw_df.empty:
            # Формируем строку ключевых слов с частотностью
            words = ", ".join([f"{r['phrase']} ({r['count']})" for _, r in kw_df.head(15).iterrows()])
            # multi_cell сама переносит слова на новую строку, если они не влезают
            self.pdf.multi_cell(0, 7, txt=words)
        else:
            self.pdf.cell(0, 7, txt="Нет данных для анализа", ln=True)
        self.pdf.ln(10)

        # --- 4. ДЕТАЛЬНЫЙ РЕЕСТР СООБЩЕНИЙ ---
        self.pdf.add_page()  # Список постов выносим на новую страницу
        self.pdf.set_font(self.font_name, 'B', 12)
        self.pdf.cell(0, 10, txt=" 3. ДЕТАЛЬНЫЙ РЕЕСТР СООБЩЕНИЙ", ln=True, fill=True)
        self.pdf.ln(5)

        # Итерируемся по сообщениям от новых к старым
        for _, row in df.sort_values(by='date', ascending=False).iterrows():
            # Проверка: если до края страницы осталось мало места — переходим на новую
            if self.pdf.get_y() > 250:
                self.pdf.add_page()

            # ШАПКА ПОСТА (Дата и Категория ИИ)
            self.pdf.set_font(self.font_name, 'B', 9)
            self.pdf.set_fill_color(240, 240, 240)  # Серый фон шапки
            header_text = f" [{row['date']}]  КАТЕГОРИЯ: {row['cluster']}"
            self.pdf.cell(0, 7, txt=header_text, ln=True, fill=True)

            # ТЕКСТ ПОСТА (Очищенный от мусора)
            self.pdf.set_font(self.font_name, size=9)
            clean_body = self.clean_text_for_pdf(str(row['text']))
            # Фиксируем ширину 185мм, чтобы текст гарантированно не ушел вправо
            self.pdf.multi_cell(185, 5, txt=clean_body[:1200])

            # СТРОКА МЕТРИК (Просмотры, Реакции, Репосты)
            self.pdf.ln(1)
            # Жестко возвращаем курсор к левому краю (15мм), чтобы метрики не улетели вправо
            self.pdf.set_x(15)
            self.pdf.set_font(self.font_name, 'B', 8)

            v = int(row.get('views', 0))
            r = int(row.get('reactions', 0))
            f = int(row.get('forwards', 0))
            metrics_txt = f"ПРОСМОТРЫ: {v} | РЕАКЦИИ: {r} | РЕПОСТЫ: {f}"

            # Печатаем метрики и переходим на новую строку (ln=1)
            self.pdf.cell(0, 7, txt=metrics_txt, ln=1)

            # Разделительная линия между сообщениями
            self.pdf.ln(2)
            self.pdf.line(10, self.pdf.get_y(), 200, self.pdf.get_y())
            self.pdf.ln(4)

        # Возвращаем «тело» PDF-файла в виде байтов для Streamlit
        return self.pdf.output()