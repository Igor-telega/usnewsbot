import logging
import os
import requests
import feedparser
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.utils.markdown import hbold
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

def fetch_news():
    url = f"https://newsapi.org/v2/top-headlines?country=us&apiKey={NEWS_API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        articles = response.json().get("articles", [])
        return articles
    else:
        print("Failed to fetch news:", response.status_code)
        return []

async def send_news():
    articles = fetch_news()
    for article in articles[:5]:  # Отправляем только 5 свежих новостей
        title = article["title"]
        url = article["url"]
        caption = f"{hbold(title)}\n\n<a href='{url}'>Read more</a>"
        try:
            await bot.send_message(chat_id=CHANNEL_ID, text=caption)
        except Exception as e:
            logging.error("Error sending news:", exc_info=e)

@dp.startup()
async def on_startup(dispatcher):
    await send_news()

if __name__ == "__main__":
    import asyncio

    async def main():
        logging.basicConfig(level=logging.INFO)
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)

    asyncio.run(main())
