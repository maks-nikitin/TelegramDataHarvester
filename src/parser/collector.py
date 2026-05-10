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

    async def fetch_messages(self, channel_username, start_date=None, end_date=None, limit=500):
        """
        Сбор данных за конкретный период.
        start_date: с какого дня собираем (самый старый)
        end_date: по какой день собираем (самый новый)
        """
        async with self.client:
            try:
                entity = await self.client.get_entity(channel_username)
                messages_data = []

                # В Telethon offset_date значит "сообщения старше этой даты"
                # Если end_date задан, начинаем поиск именно с него (двигаемся назад в прошлое)
                # Если не задан - берем самые свежие.
                offset_date = end_date + datetime.timedelta(days=1) if end_date else None

                async for msg in self.client.iter_messages(entity, limit=limit, offset_date=offset_date):
                    # Превращаем время сообщения в дату для сравнения
                    m_date = msg.date.date()

                    # 1. Если сообщение НОВЕЕ, чем наш конец периода — пропускаем (идем дальше в прошлое)
                    if end_date and m_date > end_date:
                        continue

                    # 2. Если сообщение СТАРШЕ, чем начало периода — всё, мы вышли за границы, стоп.
                    if start_date and m_date < start_date:
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
                            'views': msg.views or 0,
                            'forwards': msg.forwards or 0,
                            'reactions': reactions_count
                        })

                return messages_data
            except Exception as e:
                print(f"Ошибка парсера: {e}")
                return []