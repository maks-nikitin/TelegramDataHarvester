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
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO channels (username, title) VALUES (?, ?)", (username, title))
            conn.commit()

    def get_existing_msg_ids(self, channel_username):
        """Получаем список ID сообщений, которые УЖЕ ЕСТЬ в базе, чтобы не парсить их ИИ дважды"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT m.tg_msg_id FROM messages m 
                JOIN channels c ON m.channel_id = c.id 
                WHERE c.username = ?
            ''', (channel_username,))
            return [row[0] for row in cursor.fetchall()]

    def save_messages(self, channel_username, messages_list):
        """Сохраняем новые сообщения СРАЗУ с темами от ИИ"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM channels WHERE username = ?", (channel_username,))
            res = cursor.fetchone()
            if not res: return
            channel_id = res[0]

            for m in messages_list:
                # МАКСИМАЛЬНО ЖЕСТКАЯ ПРОВЕРКА ДАТЫ
                raw_date = m.get('date')
                # Если это объект даты Pandas, превращаем в ISO строку, иначе просто в строку
                if hasattr(raw_date, 'isoformat'):
                    date_val = raw_date.isoformat()
                else:
                    date_val = str(raw_date) if raw_date else None

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
                    m.get('cluster', 'БЕЗ ТЕМЫ')
                ))
            conn.commit()

    def get_messages_df(self):
        with sqlite3.connect(self.db_path) as conn:
            query = "SELECT m.*, c.username FROM messages m JOIN channels c ON m.channel_id = c.id"
            return pd.read_sql_query(query, conn)

    def clear_all_data(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM messages")
            conn.execute("DELETE FROM channels")
            conn.commit()