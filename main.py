import os
import json
import asyncio
import feedparser
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import InputMediaPhoto
from dotenv import load_dotenv
from embeddings_storage import is_duplicate, save_embedding
from openai import OpenAI
import numpy as np

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=TELEGRAM_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

client = OpenAI(api_key=OPENAI_API_KEY)

FEEDS = [
    "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://www.theguardian.com/world/rss",
    "http://rss.cnn.com/rss/cnn_topstories.rss"
]

TITLE_LOG = "sent_titles.json"

def load_sent_titles():
    if not os.path.exists(TITLE_LOG):
        return []
    with open(TITLE_LOG, "r") as f:
        return json.load(f)

def save_sent_titles(titles):
    with open(TITLE_LOG, "w") as f:
        json.dump(titles, f)

def clean_text(text):
    return text.replace('\xa0', ' ').strip()

def extract_publish_date(entry):
    try:
        return datetime(*entry.published_parsed[:6])
    except Exception:
        return datetime.utcnow()  # fallback

async def get_embedding(text):
    response = client.embeddings.create(
        input=text,
        model="text-embedding-3-small"
    )
    return response.data[0].embedding

async def fetch_and_send_news():
    sent_titles = load_sent_titles()
    for url in FEEDS:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            title = clean_text(entry.title)
            summary = clean_text(entry.summary) if hasattr(entry, "summary") else ""
            link = entry.link
            image_url = ""
            if "media_content" in entry and entry.media_content:
                image_url = entry.media_content[0].get("url", "")

            published_date = extract_publish_date(entry)
            if datetime.utcnow() - published_date > timedelta(hours=24):
                continue  # skip old news

            if title in sent_titles:
                continue  # skip exact duplicate

            embedding = await get_embedding(title)
            if is_duplicate(embedding):
                continue  # skip semantic duplicate

            hashtags = " ".join(f"#{tag.replace(' ', '')}" for tag in title.split()[:3])
            source = feed.feed.get("title", "News")

            text = (
                f"<b>{title}</b>\n\n"
                f"{summary}\n\n"
                f"<i>Source:</i> {source}\n"
                f"🕒 <i>Published:</i> {published_date.strftime('%B %d, %Y')}\n"
                f"{hashtags}"
            )

            try:
                if image_url:
                    await bot.send_photo(CHANNEL_ID, photo=image_url, caption=text)
                else:
                    await bot.send_message(CHANNEL_ID, text=text)
                sent_titles.append(title)
                save_sent_titles(sent_titles)
                save_embedding(title, embedding)
                await asyncio.sleep(2)
            except Exception as e:
                print(f"Error sending: {e}")

async def main():
    await fetch_and_send_news()

if __name__ == "__main__":
    asyncio.run(main())
