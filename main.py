import os
import json
import asyncio
import feedparser
import logging
from datetime import datetime, timedelta, timezone
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.utils.markdown import hbold
from dotenv import load_dotenv
from embeddings_storage import is_duplicate, save_embedding
from openai import OpenAI
from openai import AsyncOpenAI

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=TELEGRAM_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

RSS_FEEDS = {
    "NYT": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "BBC News": "https://feeds.bbci.co.uk/news/rss.xml",
    "CNN": "http://rss.cnn.com/rss/edition.rss",
    "The Guardian": "https://www.theguardian.com/world/rss",
    "Reuters": "http://feeds.reuters.com/reuters/topNews"
}

SENT_TITLES_FILE = "sent_titles.json"

def load_sent_titles():
    if os.path.exists(SENT_TITLES_FILE):
        with open(SENT_TITLES_FILE, "r") as file:
            return json.load(file)
    return []

def save_sent_titles(titles):
    with open(SENT_TITLES_FILE, "w") as file:
        json.dump(titles, file)

def clean_hashtags(title):
    return "#" + " #".join(word.capitalize().strip(".,!?") for word in title.split() if word.isalpha() and len(word) > 3)

def is_recent(entry):
    if not hasattr(entry, "published_parsed"):
        return False
    published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
    return published > datetime.now(timezone.utc) - timedelta(hours=24)

async def generate_embedding(text):
    response = await client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding

async def send_summary(title, summary, published, source_name):
    hashtags = clean_hashtags(title)
    pub_date = published.strftime("%B %d, %Y")
    message = (
        f"<b>{title}</b>\n\n"
        f"{summary}\n\n"
        f"<i>Source: {source_name}</i>\n\n"
        f"🕒 <i>Published: {pub_date}</i>\n"
        f"{hashtags}"
    )
    await bot.send_message(chat_id=CHANNEL_ID, text=message)

async def summarize_text(text):
    response = await client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Summarize the following news article in 3-4 short sentences, no title or emojis."},
            {"role": "user", "content": text}
        ],
        temperature=0.5
    )
    return response.choices[0].message.content.strip()

async def check_feeds():
    sent_titles = load_sent_titles()

    for source_name, url in RSS_FEEDS.items():
        feed = feedparser.parse(url)
        for entry in feed.entries:
            title = entry.title.strip()
            if title in sent_titles:
                continue
            if not is_recent(entry):
                continue
            content = entry.get("summary", "") or entry.get("description", "")
            full_text = f"{title}\n\n{content}"
            embedding = await generate_embedding(full_text)
            if is_duplicate(embedding):
                continue
            summary = await summarize_text(full_text)
            published_dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            await send_summary(title, summary, published_dt, source_name)
            sent_titles.append(title)
            save_embedding(title, embedding)

    save_sent_titles(sent_titles)

async def main():
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            await check_feeds()
        except Exception as e:
            logging.error(f"Error: {e}")
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())

