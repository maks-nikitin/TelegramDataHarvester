import os
from telethon.sync import TelegramClient
from dotenv import load_dotenv
import datetime

# Загружаем настройки из файла .env (API_ID и API_HASH)
# Это нужно для безопасности, чтобы не хранить секретные ключи прямо в коде
load_dotenv()


class TelegramCollector:
    """
    Класс для взаимодействия с API Telegram.
    Отвечает за подключение к серверам и сбор сообщений за нужный период.
    """

    def __init__(self, session_name='data/analyzer_session'):
        # Считываем ключи доступа из переменных окружения
        self.api_id = os.getenv("API_ID")
        self.api_hash = os.getenv("API_HASH")

        # Создаем папку data, если её еще нет (для хранения файла .session)
        os.makedirs(os.path.dirname(session_name), exist_ok=True)

        # Инициализируем клиента Telegram.
        # session_name — это "цифровой паспорт" вашего входа, чтобы не вводить СМС каждый раз.
        self.client = TelegramClient(session_name, self.api_id, self.api_hash)

    async def fetch_messages(self, channel_username, start_date=None, end_date=None, limit=500):
        """
        Асинхронный сбор данных из канала.
        channel_username: @имя_канала
        start_date: начало периода (самая старая дата)
        end_date: конец периода (самая новая дата)
        """
        # "async with" автоматически подключается к Telegram и отключается в конце
        async with self.client:
            try:
                # Получаем объект канала по его имени
                entity = await self.client.get_entity(channel_username)
                messages_data = []

                # В Telegram сообщения идут от новых к старым.
                # offset_date — это дата, С КОТОРОЙ мы начинаем смотреть историю (двигаясь назад).
                # Прибавляем 1 день к end_date, чтобы захватить последний день периода целиком.
                offset_date = end_date + datetime.timedelta(days=1) if end_date else None

                # Начинаем перебор сообщений в канале
                async for msg in self.client.iter_messages(entity, limit=limit, offset_date=offset_date):
                    # Берем только дату (без часов/минут) для сравнения
                    m_date = msg.date.date()

                    # 1. Если сообщение НОВЕЕ, чем наш конец периода — пропускаем его и идем дальше в прошлое
                    if end_date and m_date > end_date:
                        continue

                    # 2. Если сообщение СТАРШЕ, чем начало нашего периода — всё, мы вышли за границы. Стоп.
                    if start_date and m_date < start_date:
                        break

                    # Нас интересуют только текстовые посты
                    if msg.text:
                        # Считаем сумму всех реакций (лайки, огоньки и т.д.)
                        reactions_count = 0
                        if msg.reactions:
                            # API отдает реакции списком, мы их просто суммируем
                            for reaction in msg.reactions.results:
                                reactions_count += reaction.count

                        # Формируем "чистый" словарь данных для передачи в базу
                        messages_data.append({
                            'tg_msg_id': msg.id,  # Оригинальный ID поста в Telegram
                            'text': msg.text,  # Текст поста
                            'date': msg.date.replace(tzinfo=None),  # Время (убираем часовой пояс для БД)
                            'views': msg.views or 0,  # Просмотры
                            'forwards': msg.forwards or 0,  # Репосты
                            'reactions': reactions_count  # Сумма реакций
                        })

                # Возвращаем список всех найденных постов
                return messages_data
            except Exception as e:
                # Если произошла ошибка (например, канал приватный или удален) — выводим в консоль
                print(f"Ошибка парсера: {e}")
                return []