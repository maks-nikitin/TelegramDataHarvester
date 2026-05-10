from fpdf import FPDF
import datetime
import os
import re


class PDFReport:
    """
    Класс для генерации аналитических PDF-отчетов.
    Преобразует сырые данные из базы и результаты анализа ИИ
    в структурированный печатный документ.
    """

    def __init__(self):
        # Инициализируем библиотеку FPDF
        self.pdf = FPDF()
        # Настраиваем автоматический перенос на новую страницу при достижении нижнего поля (15 мм)
        self.pdf.set_auto_page_break(auto=True, margin=15)
        # Добавляем первую страницу
        self.pdf.add_page()

        # РАБОТА СО ШРИФТАМИ (Критически важно для поддержки кириллицы)
        # По умолчанию PDF-библиотеки не поддерживают русский язык.
        # Мы ищем системный шрифт Arial или загружаем DejaVu, чтобы текст отображался корректно.
        font_path = "C:\\Windows\\Fonts\\arial.ttf"
        if os.path.exists(font_path):
            self.pdf.add_font("Arial", "", font_path)
            self.pdf.add_font("Arial", "B", "C:\\Windows\\Fonts\\arialbd.ttf")  # Жирный
            self.font_name = "Arial"
        else:
            # Резервный шрифт, если Arial не найден
            self.pdf.add_font("DejaVu", "", "https://github.com/reingart/pyfpdf/raw/master/fpdf/font/DejaVuSans.ttf")
            self.pdf.add_font("DejaVu", "B",
                              "https://github.com/reingart/pyfpdf/raw/master/fpdf/font/DejaVuSans-Bold.ttf")
            self.font_name = "DejaVu"

    def clean_text_for_pdf(self, text):
        """
        Специальная очистка текста для PDF-верстки.
        Удаляет Markdown-символы и длинные ссылки, которые могут 'раздуть' таблицу
        и вытолкнуть текст за границы листа.
        """
        if not text: return ""
        # Удаляем Markdown ссылки: [текст](ссылка) -> оставляем только 'текст'
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        # Удаляем спецсимволы форматирования Telegram (звездочки, подчеркивания)
        text = text.replace('*', '').replace('_', '').replace('`', '')
        # Удаляем голые URL (http/https), так как они не переносятся и ломают верстку
        text = re.sub(r'https?://\S+', '', text)
        text = re.sub(r't\.me/\S+', '', text)
        # Оставляем только буквы, цифры и базовую пунктуацию
        text = re.sub(r'[^\w\s\.\,\!\?\-\:\(\)\"\']', ' ', text)
        return " ".join(text.split())

    def generate(self, df, kw_df, channel_name):
        """
        Основной метод сборки документа.
        Принимает:
        - df: основные данные (посты)
        - kw_df: таблицу ключевых слов
        - channel_name: название канала для заголовка
        """

        # --- ТИТУЛЬНЫЙ ЛИСТ / ЗАГОЛОВОК ---
        self.pdf.set_font(self.font_name, 'B', 16)
        self.pdf.cell(0, 15, txt=f"АНАЛИТИЧЕСКИЙ ОТЧЕТ: {channel_name.upper()}", ln=True, align='C')

        self.pdf.set_font(self.font_name, size=10)
        self.pdf.cell(0, 8, txt=f"Сформировано: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}", ln=True,
                      align='C')
        self.pdf.ln(10)

        # --- РАЗДЕЛ 1: ОБЩАЯ СТАТИСТИКА ---
        self.pdf.set_font(self.font_name, 'B', 14)
        self.pdf.set_fill_color(230, 240, 255)  # Светло-голубой фон заголовка
        self.pdf.cell(0, 10, txt=" 1. Общие показатели за период", ln=True, fill=True)

        self.pdf.set_font(self.font_name, size=11)
        self.pdf.ln(2)
        self.pdf.cell(0, 8, txt=f"Проанализировано постов: {len(df)}", ln=True)
        self.pdf.cell(0, 8, txt=f"Суммарно просмотров: {int(df['views'].sum())}", ln=True)
        self.pdf.cell(0, 8, txt=f"Суммарно реакций (лайки и т.д.): {int(df['reactions'].sum())}", ln=True)
        self.pdf.ln(5)

        # --- РАЗДЕЛ 2: КЛЮЧЕВЫЕ СЛОВА ---
        self.pdf.set_font(self.font_name, 'B', 14)
        self.pdf.cell(0, 10, txt=" 2. Топ-15 ключевых слов и трендов", ln=True, fill=True)
        self.pdf.set_font(self.font_name, size=11)
        self.pdf.ln(2)

        if kw_df is not None and not kw_df.empty:
            # Превращаем DataFrame с фразами в одну строку через запятую
            words_list = [f"{row['phrase']} ({row['count']})" for _, row in kw_df.head(15).iterrows()]
            self.pdf.multi_cell(0, 8, txt=", ".join(words_list))
        else:
            self.pdf.cell(0, 8, txt="Недостаточно данных для выделения трендов.", ln=True)
        self.pdf.ln(10)

        # --- РАЗДЕЛ 3: ДЕТАЛЬНЫЙ РЕЕСТР ---
        # Начинаем детальный список постов с новой страницы для красоты
        self.pdf.add_page()
        self.pdf.set_font(self.font_name, 'B', 14)
        self.pdf.cell(0, 10, txt=" 3. Детальный реестр сообщений", ln=True, fill=True)
        self.pdf.ln(5)

        # Перебираем сообщения от новых к старым
        for _, row in df.sort_values(by='date', ascending=False).iterrows():
            # Если дошли до конца страницы (осталось < 40мм), создаем новую
            if self.pdf.get_y() > 250:
                self.pdf.add_page()

            # "Шапка" поста: Дата и категория (выделяем фоном)
            self.pdf.set_font(self.font_name, 'B', 10)
            self.pdf.set_fill_color(245, 245, 245)
            self.pdf.cell(0, 8, txt=f" {row['date']} | КАТЕГОРИЯ: {row['cluster']}", ln=True, fill=True)

            # Текст поста (прогнанный через фильтр очистки)
            self.pdf.set_font(self.font_name, size=9)
            body = self.clean_text_for_pdf(str(row['text']))
            # multi_cell автоматически переносит длинный текст на новые строки
            self.pdf.multi_cell(185, 5, txt=body[:1000] + ("..." if len(body) > 1000 else ""))

            # Метрики эффективности поста
            self.pdf.ln(2)
            self.pdf.set_x(15)  # Принудительный сброс позиции к левому краю
            self.pdf.set_font(self.font_name, 'B', 8)
            metrics = f"ПРОСМОТРЫ: {int(row['views'])} | РЕАКЦИИ: {int(row['reactions'])} | РЕПОСТЫ: {int(row['forwards'])}"
            self.pdf.cell(0, 6, txt=metrics, ln=True)

            # Разделительная черта между сообщениями
            self.pdf.ln(2)
            self.pdf.line(10, self.pdf.get_y(), 200, self.pdf.get_y())
            self.pdf.ln(4)

        # Возвращаем готовый поток байтов PDF для скачивания пользователем
        return self.pdf.output()