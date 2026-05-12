import os
from telethon.sync import TelegramClient
from dotenv import load_dotenv
import datetime

# Загружаем переменные окружения из файла .env в систему.
# Это позволяет не "хардкодить" секретные ключи API в коде приложения,
# что является стандартом безопасности (best practice) в веб-разработке.
load_dotenv()


class TelegramCollector:
    """
    Класс-коллектор для работы с API Telegram.
    Отвечает за авторизацию клиента, подключение к каналам и
    асинхронное получение сообщений со всеми метаданными (просмотры, реакции, репосты).
    """

    def __init__(self, session_name='data/analyzer_session'):
        # Считываем API_ID и API_HASH, полученные разработчиком на my.telegram.org
        self.api_id = os.getenv("API_ID")
        self.api_hash = os.getenv("API_HASH")

        # Гарантируем, что папка для файла сессии (обычно data/) существует.
        # Если папки нет, os.makedirs её создаст.
        os.makedirs(os.path.dirname(session_name), exist_ok=True)

        # Инициализируем клиента Telethon.
        # session_name — это путь к файлу .session. В нем сохраняются ключи шифрования,
        # благодаря чему не нужно повторно проходить авторизацию через СМС при каждом запуске.
        self.client = TelegramClient(session_name, self.api_id, self.api_hash)

    async def fetch_messages(self, channel_username, start_date=None, end_date=None, limit=500):
        """
        Сбор данных за период.
        Исправлено: теперь корректно работает, если начало и конец периода — один и тот же день.
        """
        async with self.client:
            try:
                entity = await self.client.get_entity(channel_username)
                messages_data = []

                # Если даты одинаковые, нам нужно начать сбор со следующего дня (00:00),
                # чтобы захватить все сообщения за выбранное число, двигаясь назад.
                # Сдвигаем 'дату отсчета' на один день вперед.
                offset_date = end_date + datetime.timedelta(days=1) if end_date else None

                async for msg in self.client.iter_messages(entity, limit=limit, offset_date=offset_date):
                    # Превращаем время сообщения (UTC) в дату
                    m_date = msg.date.date()

                    # 1. Если сообщение НОВЕЕ, чем наш конец периода — пропускаем
                    # (хотя благодаря offset_date выше, таких почти не будет)
                    if end_date and m_date > end_date:
                        continue

                    # 2. Если сообщение СТАРШЕ, чем начало периода — СТОП.
                    # Но если m_date == start_date, мы ДОЛЖНЫ его забрать.
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
                            'date': msg.date.replace(tzinfo=None),  # Убираем таймзону для БД
                            'views': msg.views or 0,
                            'forwards': msg.forwards or 0,
                            'reactions': reactions_count
                        })

                return messages_data
            except Exception as e:
                print(f"Ошибка парсера: {e}")
                return []