import asyncio
from src.parser.collector import TelegramCollector

async def main():
    collector = TelegramCollector()
    print("Пробуем подключиться к Telegram...")
    # При первом запуске в терминале попросят номер телефона и код из ТГ
    messages = await collector.fetch_messages('@telegram', limit=5)
    print(f"Успех! Собрано {len(messages)} сообщений.")
    for m in messages:
        print(f"- {m['text'][:50]}...")

if __name__ == "main":
    asyncio.run(main())