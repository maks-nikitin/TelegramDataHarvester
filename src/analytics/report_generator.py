from fpdf import FPDF
import datetime
import os
import re


class PDFReport:
    def __init__(self):
        self.pdf = FPDF()
        self.pdf.set_auto_page_break(auto=True, margin=20)
        self.pdf.add_page()

        # Поиск шрифтов
        font_path = "C:\\Windows\\Fonts\\arial.ttf"
        if os.path.exists(font_path):
            self.pdf.add_font("Arial", "", font_path)
            self.pdf.add_font("Arial", "B", "C:\\Windows\\Fonts\\arialbd.ttf")
            self.font_name = "Arial"
        else:
            self.pdf.add_font("DejaVu", "", "https://github.com/reingart/pyfpdf/raw/master/fpdf/font/DejaVuSans.ttf")
            self.pdf.add_font("DejaVu", "B",
                              "https://github.com/reingart/pyfpdf/raw/master/fpdf/font/DejaVuSans-Bold.ttf")
            self.font_name = "DejaVu"

    def clean_text_for_pdf(self, text):
        """Агрессивная очистка текста для стабильной верстки в PDF"""
        if not text: return ""
        # Удаляем всё, что похоже на ссылки (http, https, t.me, ссылки в скобках)
        text = re.sub(r'https?://\S+', '', text)
        text = re.sub(r't\.me/\S+', '', text)
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        # Удаляем спецсимволы разметки
        text = text.replace('*', '').replace('_', '').replace('`', '')
        # Оставляем только базовый набор символов (буквы, цифры, знаки препинания)
        # Это защитит от 'невидимых' символов, ломающих ширину строки
        text = re.sub(r'[^\w\s\.\,\!\?\-\:\(\)\"\']', ' ', text)
        return " ".join(text.split())  # Убираем лишние пробелы и переносы

    def generate(self, df, kw_df, channel_name):
        # 1. ТИТУЛЬНЫЙ ЛИСТ
        self.pdf.set_font(self.font_name, 'B', 16)
        self.pdf.cell(0, 10, txt=f"ОТЧЕТ: {channel_name.upper()}", ln=True, align='C')
        self.pdf.set_font(self.font_name, size=10)
        self.pdf.cell(0, 8, txt=f"Дата создания: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}", ln=True,
                      align='C')
        self.pdf.ln(10)

        # 2. СТАТИСТИКА
        self.pdf.set_font(self.font_name, 'B', 12)
        self.pdf.set_fill_color(200, 220, 255)
        self.pdf.cell(0, 10, txt=" 1. СВОДНЫЕ ПОКАЗАТЕЛИ", ln=True, fill=True)
        self.pdf.set_font(self.font_name, size=10)
        self.pdf.ln(2)
        self.pdf.cell(0, 7, txt=f"Проанализировано сообщений: {len(df)}", ln=True)
        self.pdf.cell(0, 7, txt=f"Общее кол-во просмотров: {int(df['views'].sum())}", ln=True)
        self.pdf.cell(0, 7, txt=f"Общее кол-во реакций: {int(df['reactions'].sum())}", ln=True)
        self.pdf.ln(10)

        # 3. КЛЮЧЕВЫЕ СЛОВА
        self.pdf.set_font(self.font_name, 'B', 12)
        self.pdf.cell(0, 10, txt=" 2. КЛЮЧЕВЫЕ СЛОВА (ТОП-15)", ln=True, fill=True)
        self.pdf.set_font(self.font_name, size=10)
        self.pdf.ln(2)
        if kw_df is not None and not kw_df.empty:
            words = ", ".join([f"{r['phrase']} ({r['count']})" for _, r in kw_df.head(15).iterrows()])
            self.pdf.multi_cell(0, 7, txt=words)
        else:
            self.pdf.cell(0, 7, txt="Нет данных для анализа", ln=True)
        self.pdf.ln(10)

        # 4. СПИСОК СООБЩЕНИЙ
        self.pdf.add_page()
        self.pdf.set_font(self.font_name, 'B', 12)
        self.pdf.cell(0, 10, txt=" 3. ДЕТАЛЬНЫЙ РЕЕСТР СООБЩЕНИЙ", ln=True, fill=True)
        self.pdf.ln(5)

        for _, row in df.sort_values(by='date', ascending=False).iterrows():
            # Проверка: не пора ли переходить на новую страницу?
            if self.pdf.get_y() > 250:
                self.pdf.add_page()

            # ШАПКА ПОСТА (Дата и Категория)
            self.pdf.set_font(self.font_name, 'B', 9)
            self.pdf.set_fill_color(240, 240, 240)
            header_text = f" [{row['date']}]  КАТЕГОРИЯ: {row['cluster']}"
            self.pdf.cell(0, 7, txt=header_text, ln=True, fill=True)

            # ТЕКСТ ПОСТА
            self.pdf.set_font(self.font_name, size=9)
            clean_body = self.clean_text_for_pdf(str(row['text']))
            # Ограничиваем ширину (180мм вместо 0), чтобы текст точно не ушел вправо
            self.pdf.multi_cell(185, 5, txt=clean_body[:1200])

            # СТРОКА МЕТРИК (Самое важное исправление здесь!)
            self.pdf.ln(1)  # Небольшой отступ вниз
            self.pdf.set_x(15)  # ПРИНУДИТЕЛЬНО возвращаемся к левому краю
            self.pdf.set_font(self.font_name, 'B', 8)

            # Формируем строку метрик
            v = int(row.get('views', 0))
            r = int(row.get('reactions', 0))
            f = int(row.get('forwards', 0))
            metrics_txt = f"ПРОСМОТРЫ: {v} | РЕАКЦИИ: {r} | РЕПОСТЫ: {f}"

            # Печатаем метрики с принудительным переносом строки (ln=1)
            self.pdf.cell(0, 7, txt=metrics_txt, ln=1)

            # Разделитель
            self.pdf.ln(2)
            self.pdf.line(10, self.pdf.get_y(), 200, self.pdf.get_y())
            self.pdf.ln(4)

        return self.pdf.output()