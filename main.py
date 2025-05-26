import os
import json
import feedparser
import logging
import asyncio
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types

load_dotenv()

# Константы
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")
RSS_FEED_URL = "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"
SENT_TITLES_FILE = "/data/sent_titles.json"

# Настройка логов
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Работа с сохранёнными заголовками
def load_sent_titles():
    if not os.path.exists(SENT_TITLES_FILE):
        with open(SENT_TITLES_FILE, "w") as f:
            json.dump({"titles": []}, f)
    with open(SENT_TITLES_FILE, "r") as f:
        return json.load(f)["titles"]

def save_sent_titles(titles):
    with open(SENT_TITLES_FILE, "w") as f:
        json.dump({"titles": titles}, f)

# Отправка новостей
async def send_news():
    sent_titles = load_sent_titles()
    feed = feedparser.parse(RSS_FEED_URL)

    for entry in feed.entries:
        title = entry.title
        link = entry.link
        summary = entry.summary if hasattr(entry, "summary") else ""

        if title not in sent_titles:
            text = f"<b>{title}</b>\n\n{summary}\n\n<a href='{link}'>Read more</a>"
            try:
                await bot.send_message(chat_id=CHANNEL_ID, text=text, parse_mode="HTML", disable_web_page_preview=False)
                sent_titles.append(title)
                save_sent_titles(sent_titles)
                await asyncio.sleep(2)  # антифлуд
            except Exception as e:
                logger.error(f"Error sending news: {e}")

# Главный цикл
async def main():
    while True:
        await send_news()
        await asyncio.sleep(300)  # каждые 5 минут

if __name__ == "__main__":
    asyncio.run(main())
