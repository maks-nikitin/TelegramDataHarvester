import os
from telethon.sync import TelegramClient
from dotenv import load_dotenv
import datetime

load_dotenv()


class TelegramCollector:
    def __init__(self, session_name='data/analyzer_session'):
        self.api_id = os.getenv("API_ID")
        self.api_hash = os.getenv("API_HASH")
        # Создаем клиента. Файл сессии будет храниться в папке data
        self.client = TelegramClient(session_name, self.api_id, self.api_hash)

    async def fetch_messages(self, channel_username, limit=50):
        """Сбор сообщений из указанного канала"""
        async with self.client:
            try:
                # Получаем объект канала
                entity = await self.client.get_entity(channel_username)
                messages_data = []

                async for msg in self.client.iter_messages(entity, limit=limit):
                    # Собираем только текстовые сообщения
                    if msg.text:
                        # Считаем сумму реакций, если они есть
                        reactions_count = 0
                        if msg.reactions:
                            for reaction in msg.reactions.results:
                                reactions_count += reaction.count

                        data = {
                            'text': msg.text,
                            'date': msg.date.replace(tzinfo=None),  # Убираем таймзону для БД
                            'views': msg.views or 0,
                            'forwards': msg.forwards or 0,
                            'reactions': reactions_count
                        }
                        messages_data.append(data)

                return messages_data
            except Exception as e:
                print(f"Ошибка при сборе данных из {channel_username}: {e}")
                return []