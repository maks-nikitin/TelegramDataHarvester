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
        Асинхронный метод сбора сообщений из конкретного канала за указанный период.

        Параметры:
          - channel_username (str): имя канала (например, 'grodnonews')
          - start_date (datetime.date): начало периода анализа (самая старая дата)
          - end_date (datetime.date): конец периода анализа (самая новая дата)
          - limit (int): максимальное число постов за один запрос (чтобы не перегружать память)
        """
        # "async with" автоматически открывает соединение с Telegram и корректно закрывает его
        # по окончании работы блока кода, даже если внутри произойдет критическая ошибка.
        async with self.client:
            try:
                # Получаем сущность (объект) канала/группы по его юзернейму
                entity = await self.client.get_entity(channel_username)
                messages_data = []

                # Telegram API выдает посты в обратном порядке (от новых к старым).
                # В Telethon параметр offset_date означает "начни сбор с постов старше этой даты".
                # Если конечная дата задана, мы прибавляем 1 день и начинаем сканирование с этого момента.
                offset_date = end_date + datetime.timedelta(days=1) if end_date else None

                # Асинхронно перебираем сообщения из канала (генератор iter_messages)
                async for msg in self.client.iter_messages(entity, limit=limit, offset_date=offset_date):
                    # Извлекаем дату сообщения (без часового пояса для простоты сравнения)
                    m_date = msg.date.date()

                    # КРИТЕРИЙ 1: Если сообщение новее, чем конец нашего периода, пропускаем его
                    # и продолжаем листать историю дальше в прошлое (назад во времени).
                    if end_date and m_date > end_date:
                        continue

                    # КРИТЕРИЙ 2: Если мы дошли до сообщений, которые старше начала нашего периода —
                    # мы вышли за границы нужного диапазона дат. Сбор можно досрочно остановить (break).
                    if start_date and m_date < start_date:
                        break

                    # Нас интересуют только текстовые сообщения (пропускаем посты, состоящие только из картинок/видео)
                    if msg.text:
                        # Сбор реакций на сообщение
                        reactions_count = 0
                        if msg.reactions:
                            # Суммируем количество каждого типа реакций (лайки, сердечки, смайлики)
                            for reaction in msg.reactions.results:
                                reactions_count += reaction.count

                        # Формируем очищенный словарь метаданных поста
                        messages_data.append({
                            'tg_msg_id': msg.id,  # Уникальный ID поста внутри канала
                            'text': msg.text,  # Исходный текст поста
                            'date': msg.date.replace(tzinfo=None),  # Время публикации (без таймзоны)
                            'views': msg.views or 0,  # Просмотры (для приватных групп вернет 0)
                            'forwards': msg.forwards or 0,  # Пересылки / Репосты
                            'reactions': reactions_count  # Сумма всех реакций
                        })

                # Возвращаем массив собранных данных
                return messages_data

            except Exception as e:
                # Если возникла сетевая ошибка или канал заблокирован — выводим лог в консоль
                print(f"Ошибка парсера: {e}")
                return []