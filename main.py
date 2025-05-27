import os
import json
import asyncio
import feedparser
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from embeddings_storage import is_duplicate, save_embedding
from openai import OpenAI

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=TELEGRAM_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

client = OpenAI(api_key=OPENAI_API_KEY)

RSS_FEEDS = {
    "NY Times": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "BBC News": "https://feeds.bbci.co.uk/news/rss.xml",
    "The Guardian": "https://www.theguardian.com/world/rss",
    "CNN": "http://rss.cnn.com/rss/cnn_topstories.rss"
}

SENT_TITLES_FILE = "sent_titles.json"

def load_sent_titles():
    if not os.path.exists(SENT_TITLES_FILE):
        return []
    with open(SENT_TITLES_FILE, "r") as file:
        return json.load(file)

def save_sent_title(title):
    titles = load_sent_titles()
    titles.append(title)
    with open(SENT_TITLES_FILE, "w") as file:
        json.dump(titles, file)

async def get_embedding(text):
    response = client.embeddings.create(
        input=text,
        model="text-embedding-ada-002"
    )
    return response.data[0].embedding

def format_datetime(dt):
    return dt.strftime("%B %d, %Y")

async def process_feed():
    sent_titles = load_sent_titles()
    for source_name, url in RSS_FEEDS.items():
        feed = feedparser.parse(url)
        for entry in feed.entries:
            title = entry.get("title", "")
            if title in sent_titles:
                continue

            published_parsed = entry.get("published_parsed")
            if not published_parsed:
                continue

            published = datetime(*published_parsed[:6])
            if datetime.utcnow() - published > timedelta(days=1):
                continue

            summary = entry.get("summary", "")
            full_text = f"{title}. {summary}"

            embedding = await get_embedding(full_text)
            if is_duplicate(embedding):
                continue

            image_url = ""
            if "media_content" in entry and entry.media_content:
                image_url = entry.media_content[0].get("url", "")
            elif "links" in entry:
                for link in entry.links:
                    if link.get("type", "").startswith("image"):
                        image_url = link.get("href", "")
                        break

            hashtags = "#" + " #".join([word for word in title.split() if word.istitle() and len(word) > 3])
            message = f"<b>{title}</b>\n\n{summary}\n\n"
            message += f"<i>Source:</i> {source_name}\n"
            message += f"\n<b>🕒 Published:</b> {format_datetime(published)}"
            if hashtags.strip() != "#":
                message += f"\n\n{hashtags}"

            if image_url:
                await bot.send_photo(chat_id=CHANNEL_ID, photo=image_url, caption=message)
            else:
                await bot.send_message(chat_id=CHANNEL_ID, text=message)

            save_sent_title(title)
            save_embedding(title, embedding)
            await asyncio.sleep(2)

async def main():
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            await process_feed()
        except Exception as e:
            logging.exception("Error while processing feed:")
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
