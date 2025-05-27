import os
import json
import logging
import feedparser
import requests
import time
from datetime import datetime, timedelta
import openai
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from tiktoken import encoding_for_model
from embeddings import get_embedding, is_duplicate, save_embedding
from image_gen import generate_image

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
openai.api_key = os.getenv("OPENAI_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

NEWS_SOURCES = {
    "NYT": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "CNN": "http://rss.cnn.com/rss/edition.rss",
    "BBC": "http://feeds.bbci.co.uk/news/rss.xml"
}

sent_titles_path = "sent_titles.json"
try:
    with open(sent_titles_path, "r") as f:
        sent_titles = json.load(f)
except FileNotFoundError:
    sent_titles = {}

def get_recent_entries(url, hours=24):
    feed = feedparser.parse(url)
    entries = []
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    for entry in feed.entries:
        published = entry.get("published_parsed") or entry.get("updated_parsed")
        if not published:
            continue
        published_dt = datetime(*published[:6])
        if published_dt > cutoff:
            entries.append(entry)
    return entries

def count_tokens(text):
    enc = encoding_for_model("text-embedding-3-small")
    return len(enc.encode(text))

async def summarize(title, content, source):
    prompt = (
        f"Summarize the news article from {source} with the title:"
        f""{title}"

"
        f"Content:
"{content}"

"
        "Write a short news-style summary for an American audience in 7-10 sentences. "
        "Keep it neutral and journalistic. If the title is already a headline, do not repeat it. "
        "Do not include any URLs or source names."
    )

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    return response.choices[0].message["content"].strip()

async def process_feed():
    for i, (source, url) in enumerate(NEWS_SOURCES.items()):
        entries = get_recent_entries(url)
        for j, entry in enumerate(entries):
            title = entry.get("title", "")
            summary = entry.get("summary", "")
            if not title or not summary or count_tokens(title) > 100:
                continue

            if title in sent_titles.get(source, []):
                continue

            embedding = get_embedding(title)
            if is_duplicate(embedding, sent_titles.get("embeddings", [])):
                continue

            content = f"{title}

{await summarize(title, summary, source)}"
            image = generate_image(title)

            await bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=image,
                caption=content[:1024]
            )

            sent_titles.setdefault(source, []).append(title)
            sent_titles.setdefault("embeddings", []).append(embedding.tolist())
            save_embedding(title, embedding)

            with open(sent_titles_path, "w") as f:
                json.dump(sent_titles, f)

            time.sleep(2)

if __name__ == "__main__":
    import asyncio
    asyncio.run(process_feed())
