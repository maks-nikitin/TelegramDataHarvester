import os
from telethon.sync import TelegramClient
from dotenv import load_dotenv
import datetime

load_dotenv()


class TelegramCollector:
    def __init__(self, session_name='data/analyzer_session'):
        self.api_id = os.getenv("API_ID")
        self.api_hash = os.getenv("API_HASH")
        os.makedirs(os.path.dirname(session_name), exist_ok=True)
        self.client = TelegramClient(session_name, self.api_id, self.api_hash)

    async def fetch_messages(self, channel_username, start_date=None, limit=100):
        """Сбор данных за период (start_date)"""
        async with self.client:
            try:
                entity = await self.client.get_entity(channel_username)
                messages_data = []

                # offset_date — это дата, С КОТОРОЙ мы начинаем смотреть назад
                # reverse=True + offset_date позволят собрать данные ЗА ПЕРИОД
                async for msg in self.client.iter_messages(entity, limit=limit, offset_date=None):

                    # Если мы дошли до сообщений старше, чем выбранная дата — стоп
                    if start_date and msg.date.date() < start_date:
                        break

                    if msg.text:
                        reactions_count = 0
                        if msg.reactions:
                            for reaction in msg.reactions.results:
                                reactions_count += reaction.count

                        messages_data.append({
                            'tg_msg_id': msg.id,
                            'text': msg.text,
                            'date': msg.date.replace(tzinfo=None),
                            'views': msg.views or 0,  # В группах будет 0
                            'forwards': msg.forwards or 0,
                            'reactions': reactions_count
                        })

                return messages_data
            except Exception as e:
                print(f"Ошибка парсера: {e}")
                return []