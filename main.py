import logging
import json
import feedparser
import os
from aiogram import Bot, Dispatcher, types
from aiogram.enums.parse_mode import ParseMode
from aiogram.types import FSInputFile
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.utils.markdown import hlink
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram import F

from openai import OpenAI
from datetime import datetime

NEWS_FEED_URL = "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"
POSTED_TITLES_FILE = "/data/sent_titles.json"

# Load environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML, session=AiohttpSession())
dp = Dispatcher(storage=MemoryStorage())

client = OpenAI(api_key=OPENAI_API_KEY)


def load_posted_titles():
    if os.path.exists(POSTED_TITLES_FILE):
        with open(POSTED_TITLES_FILE, "r") as f:
            data = json.load(f)
            return set(data.get("titles", []))
    return set()


def save_posted_titles(titles):
    with open(POSTED_TITLES_FILE, "w") as f:
        json.dump({"titles": list(titles)}, f)


def summarize(text):
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You summarize news headlines."},
                {"role": "user", "content": f"Summarize this news in one short sentence: {text}"}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        logging.error(f"Error summarizing: {e}")
        return None


async def post_news():
    feed = feedparser.parse(NEWS_FEED_URL)
    posted_titles = load_posted_titles()

    for entry in feed.entries[:5]:  # Limit to 5 latest
        title = entry.title
        link = entry.link

        if title in posted_titles:
            continue

        summary = summarize(title)
        if summary:
            message = f"{hlink(title, link)}\n\n{summary}"
            try:
                await bot.send_message(chat_id=CHANNEL_ID, text=message)
                posted_titles.add(title)
            except Exception as e:
                logging.error(f"Error sending news: {e}")

    save_posted_titles(posted_titles)


@dp.startup()
async def on_startup(dispatcher: Dispatcher) -> None:
    await post_news()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    dp.run_polling(bot)
