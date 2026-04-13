import sqlite3
import pandas as pd

class DBManager:
    def __init__(self, db_path="data/bot_database.db"):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE,
                    title TEXT
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id INTEGER,
                    text TEXT,
                    date TIMESTAMP,
                    views INTEGER,
                    forwards INTEGER,
                    reactions INTEGER,
                    cluster TEXT,
                    FOREIGN KEY (channel_id) REFERENCES channels (id)
                )
            ''')
            conn.commit()

    def add_channel(self, username, title=""):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO channels (username, title) VALUES (?, ?)", (username, title))
            conn.commit()

    def save_messages(self, channel_username, messages_list):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Получаем ID канала по юзернейму
            cursor.execute("SELECT id FROM channels WHERE username = ?", (channel_username,))
            res = cursor.fetchone()
            if not res: return
            channel_id = res[0]

            for m in messages_list:
                cursor.execute('''
                    INSERT INTO messages (channel_id, text, date, views, forwards, reactions)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (channel_id, m['text'], m['date'], m['views'], m['forwards'], m['reactions']))
            conn.commit()

    def get_messages_df(self):
        """Возвращает все сообщения в виде Pandas DataFrame для анализа"""
        with sqlite3.connect(self.db_path) as conn:
            query = '''
                SELECT m.*, c.username 
                FROM messages m 
                JOIN channels c ON m.channel_id = c.id
            '''
            return pd.read_sql_query(query, conn)

    def clear_all_data(self):
        """Полная очистка всех таблиц в базе данных"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Удаляем данные, но сохраняем сами таблицы
            cursor.execute("DELETE FROM messages")
            cursor.execute("DELETE FROM channels")
            conn.commit()