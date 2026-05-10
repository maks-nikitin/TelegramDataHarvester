import sqlite3
import pandas as pd


class DBManager:
    """
    Класс для управления базой данных SQLite.
    Отвечает за создание таблиц, сохранение каналов и сообщений,
    а также за выгрузку данных для аналитики.
    """

    def __init__(self, db_path="data/bot_database.db"):
        # Путь к файлу базы данных. Если файла нет, SQLite создаст его автоматически.
        self.db_path = db_path
        # Инициализируем структуру таблиц при создании объекта класса
        self.init_db()

    def init_db(self):
        """Создание структуры таблиц, если они еще не существуют"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Таблица 'channels': хранит информацию о мониторенных источниках
            # username — уникальный идентификатор канала (например, 'news_channel')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE,
                    title TEXT
                )
            ''')

            # Таблица 'messages': основное хранилище постов
            # UNIQUE(channel_id, tg_msg_id) — гарантирует, что один и тот же пост
            # не сохранится дважды (защита от дубликатов при повторном парсинге).
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id INTEGER,
                    tg_msg_id INTEGER, 
                    text TEXT,
                    date TIMESTAMP,
                    views INTEGER,
                    forwards INTEGER,
                    reactions INTEGER,
                    cluster TEXT,
                    UNIQUE(channel_id, tg_msg_id),
                    FOREIGN KEY (channel_id) REFERENCES channels (id)
                )
            ''')
            conn.commit()

    def add_channel(self, username, title=""):
        """Добавление нового канала в список отслеживаемых"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # INSERT OR IGNORE — если канал уже есть, ошибка не вылетит, запись просто пропустится
            cursor.execute("INSERT OR IGNORE INTO channels (username, title) VALUES (?, ?)", (username, title))
            conn.commit()

    def get_existing_msg_ids(self, channel_username):
        """
        Возвращает список ID сообщений, которые уже сохранены в базе для конкретного канала.
        Это нужно парсеру, чтобы не тратить ресурсы ИИ на обработку уже известных постов.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT m.tg_msg_id FROM messages m 
                JOIN channels c ON m.channel_id = c.id 
                WHERE c.username = ?
            ''', (channel_username,))
            return [row[0] for row in cursor.fetchall()]

    def save_messages(self, channel_username, messages_list):
        """
        Сохранение списка обработанных сообщений в базу данных.
        Принимает список словарей (или записей DataFrame).
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Сначала находим внутренний ID канала по его юзернейму
            cursor.execute("SELECT id FROM channels WHERE username = ?", (channel_username,))
            res = cursor.fetchone()
            if not res: return
            channel_id = res[0]

            for m in messages_list:
                # Обработка даты: приводим к формату строки ISO (ГГГГ-ММ-ДД ЧЧ:ММ:СС)
                # Это важно для правильной сортировки и фильтрации в будущем.
                raw_date = m.get('date')
                if hasattr(raw_date, 'isoformat'):
                    date_val = raw_date.isoformat()
                else:
                    date_val = str(raw_date) if raw_date else None

                # Вставляем данные. Если такой tg_msg_id для этого канала уже есть,
                # запись будет проигнорирована (благодаря UNIQUE в структуре таблицы).
                cursor.execute('''
                    INSERT OR IGNORE INTO messages (channel_id, tg_msg_id, text, date, views, forwards, reactions, cluster)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    channel_id,
                    m.get('tg_msg_id'),
                    m.get('text'),
                    date_val,
                    m.get('views'),
                    m.get('forwards', 0),
                    m.get('reactions'),
                    m.get('cluster', 'БЕЗ ТЕМЫ')  # Тема, определенная нейросетью
                ))
            conn.commit()

    def get_messages_df(self):
        """
        Загрузка всех сообщений из базы в формате Pandas DataFrame.
        Используется в app.py для отрисовки графиков и таблиц.
        """
        with sqlite3.connect(self.db_path) as conn:
            # SQL-запрос с объединением (JOIN), чтобы получить текст сообщения вместе с именем канала
            query = "SELECT m.*, c.username FROM messages m JOIN channels c ON m.channel_id = c.id"
            return pd.read_sql_query(query, conn)

    def get_all_channels(self):
        """Получение списка всех юзернеймов каналов, которые хранятся в базе"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT username FROM channels")
            return [row[0] for row in cursor.fetchall()]

    def clear_all_data(self):
        """Полная очистка базы данных (удаление всех записей)"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM messages")
            conn.execute("DELETE FROM channels")
            conn.commit()