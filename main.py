import os
import feedparser
import asyncio
import openai
import tiktoken
import numpy as np
from datetime import datetime, timedelta, timezone
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from dotenv import load_dotenv
from image_gen import generate_image
from embeddings import get_embedding, is_duplicate, save_embedding

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

openai.api_key = OPENAI_API_KEY
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

sent_titles_file = "sent_titles.json"
if os.path.exists(sent_titles_file):
    import json
    with open(sent_titles_file, "r") as f:
        sent_titles = set(json.load(f))
else:
    sent_titles = set()

sources = {
    "NYT": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "BBC News": "http://feeds.bbci.co.uk/news/rss.xml",
    "CNN": "http://rss.cnn.com/rss/edition.rss"
}

def clean_source_name(name):
    return name.replace(".com", "").replace("CNN", "CNN").replace("NYT", "NYT")

def format_hashtags(title):
    return ' '.join(f"#{word.strip('.').capitalize()}" for word in title.split() if word.istitle() and len(word) > 2)

async def summarize(text):
    prompt = (
        "Summarize this news article into a concise, professional paragraph (8–10 sentences) for a U.S. audience. "
        "Keep the tone neutral and journalistic:\n\n" + text
    )
    response = await openai.ChatCompletion.acreate(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

async def send_news():
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)

    feeds = {source: feedparser.parse(url) for source, url in sources.items()}
    max_items = min(len(feed.entries) for feed in feeds.values())

    for i in range(max_items):
        for source, feed in feeds.items():
            if i >= len(feed.entries):
                continue

            entry = feed.entries[i]
            title = entry.title.strip()

            if title in sent_titles:
                continue

            pub_date = entry.get("published_parsed") or entry.get("updated_parsed")
            if not pub_date:
                continue
            pub_datetime = datetime(*pub_date[:6], tzinfo=timezone.utc)
            if pub_datetime < yesterday:
                continue

            summary = await summarize(entry.get("summary", title))
            hashtags = format_hashtags(title)

            image_url = entry.get("media_content", [{}])[0].get("url") or entry.get("image", {}).get("href")
            if not image_url:
                image_url = await generate_image(title)

            message = (
                f"<b>{title}</b>\n\n"
                f"{summary}\n\n"
                f"<b>Source:</b> {clean_source_name(source)}\n"
                f"<b>Published:</b> {pub_datetime.strftime('%a, %d %b %Y %H:%M UTC')}\n"
                f"{hashtags}"
            )

            try:
                await bot.send_photo(CHANNEL_ID, photo=image_url, caption=message, parse_mode=ParseMode.HTML)
                print(f"Sent: {title}")
                sent_titles.add(title)
                embedding = get_embedding(title)
                save_embedding(title, embedding)
            except Exception as e:
                print(f"Failed to send: {e}")

    with open(sent_titles_file, "w") as f:
        json.dump(list(sent_titles), f)

if __name__ == "__main__":
    asyncio.run(send_news())

