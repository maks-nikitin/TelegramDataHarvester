import sqlite3
import pandas as pd


class DBManager:
    """
    Класс для управления базой данных SQLite.
    Отвечает за создание таблиц, сохранение каналов и сообщений,
    а также за фильтрацию дубликатов.
    """

    def __init__(self, db_path="data/bot_database.db"):
        # Путь к файлу базы данных
        self.db_path = db_path
        # При создании объекта сразу проверяем/создаем таблицы
        self.init_db()

    def init_db(self):
        """Создает структуру таблиц в БД, если их еще нет"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Таблица каналов: хранит юзернейм и название (title)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE,
                    title TEXT
                )
            ''')

            # Таблица сообщений: самое важное место.
            # UNIQUE(channel_id, tg_msg_id) — это "предохранитель".
            # Он запрещает сохранять один и тот же пост одного канала дважды.
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
        """Добавляет новый канал в базу. Если такой уже есть — ничего не делает (IGNORE)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO channels (username, title) VALUES (?, ?)", (username, title))
            conn.commit()

    def get_existing_msg_ids(self, channel_username):
        """
        Возвращает список ID всех сообщений конкретного канала, которые уже лежат в базе.
        Это нужно для того, чтобы парсер не анализировал их повторно через нейросеть.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT m.tg_msg_id FROM messages m 
                JOIN channels c ON m.channel_id = c.id 
                WHERE c.username = ?
            ''', (channel_username,))
            # Возвращаем простой список ID-шников
            return [row[0] for row in cursor.fetchall()]

    def save_messages(self, channel_username, messages_list):
        """
        Сохраняет пакет новых сообщений в базу.
        channel_username: имя канала
        messages_list: список словарей с данными постов (текст, дата, метрики)
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Сначала находим внутренний ID канала в нашей БД по его юзернейму
            cursor.execute("SELECT id FROM channels WHERE username = ?", (channel_username,))
            res = cursor.fetchone()
            if not res: return
            channel_id = res[0]

            for m in messages_list:
                # Превращаем дату в ISO строку (ГГГГ-ММ-ДД...), чтобы SQLite мог её хранить
                raw_date = m.get('date')
                if hasattr(raw_date, 'isoformat'):
                    date_val = raw_date.isoformat()
                else:
                    date_val = str(raw_date) if raw_date else None

                # Записываем пост. Если ID сообщения уже есть — INSERT OR IGNORE его пропустит.
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
                    m.get('cluster', 'БЕЗ ТЕМЫ')  # Категория, которую определил ИИ
                ))
            conn.commit()

    def get_messages_df(self):
        """Выгружает ВСЕ данные из базы в формате Pandas DataFrame для отрисовки в UI"""
        with sqlite3.connect(self.db_path) as conn:
            # SQL запрос объединяет таблицы, чтобы мы видели имя канала рядом с текстом поста
            query = "SELECT m.*, c.username FROM messages m JOIN channels c ON m.channel_id = c.id"
            return pd.read_sql_query(query, conn)

    def get_all_channels(self):
        """Возвращает список всех каналов, которые мы когда-либо парсили"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT username FROM channels")
            return [row[0] for row in cursor.fetchall()]

    def clear_all_data(self):
        """Полная очистка базы данных (используется кнопкой в интерфейсе)"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM messages")
            conn.execute("DELETE FROM channels")
            conn.commit()