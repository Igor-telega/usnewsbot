import logging
import json
import time
import requests
import feedparser
import os

from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.utils.markdown import hbold
from aiogram.types import InputFile
from dotenv import load_dotenv
from openai import OpenAI
from io import BytesIO

# Загрузка .env
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID")

client = OpenAI(api_key=OPENAI_API_KEY)

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

RSS_FEEDS = [
    ("https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml", "NYT"),
    ("http://rss.cnn.com/rss/cnn_topstories.rss", "CNN"),
    ("https://feeds.npr.org/1001/rss.xml", "NPR"),
    ("https://www.reutersagency.com/feed/?best-topics=top-news", "Reuters"),
    ("https://www.theguardian.com/world/rss", "The Guardian")
]

SENT_TITLES_FILE = "sent_titles.json"
MAX_POSTS = 5

def load_sent_titles():
    if not os.path.exists(SENT_TITLES_FILE):
        return []
    with open(SENT_TITLES_FILE, "r") as f:
        return json.load(f).get("titles", [])

def save_sent_titles(titles):
    with open(SENT_TITLES_FILE, "w") as f:
        json.dump({"titles": titles}, f)

def summarize_text(text):
    prompt = f"Summarize this news article in 2–4 sentences as a news brief for Telegram:\n\n{text}"
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"OpenAI error: {e}")
        return None

async def fetch_and_send_news():
    sent_titles = load_sent_titles()
    new_titles = []

    for url, source in RSS_FEEDS:
        feed = feedparser.parse(url)
        count = 0
        for entry in feed.entries:
            title = entry.title
            if title in sent_titles or count >= MAX_POSTS:
                continue
            summary_text = summarize_text(entry.summary)
            if not summary_text:
                continue

            image_url = entry.media_content[0]["url"] if "media_content" in entry else None
            hashtags = " ".join(f"#{tag.strip().replace(' ', '')}" for tag in title.split() if tag.istitle())

            caption = (
                f"<b>{title}</b>\n\n"
                f"{summary_text}\n\n"
                f"<i>{source} > Top Stories</i>\n"
                f"{hashtags}"
            )

            if image_url:
                try:
                    image_data = requests.get(image_url).content
                    image_file = BytesIO(image_data)
                    image_file.name = "image.jpg"
                    await bot.send_photo(chat_id=CHANNEL_ID, photo=image_file, caption=caption)
                except Exception as e:
                    logging.warning(f"Image failed: {e}")
                    await bot.send_message(chat_id=CHANNEL_ID, text=caption)
            else:
                await bot.send_message(chat_id=CHANNEL_ID, text=caption)

            new_titles.append(title)
            count += 1

    sent_titles += new_titles
    save_sent_titles(sent_titles[:100])  # Храним только последние 100 заголовков

async def main():
    while True:
        await fetch_and_send_news()
        await asyncio.sleep(3600)  # раз в час

if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
