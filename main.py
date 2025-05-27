import os
import json
import feedparser
import asyncio
import tiktoken
import numpy as np
from datetime import datetime
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.types import InputMediaPhoto
from openai import OpenAI

from embeddings_storage import is_duplicate, save_embedding

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=TELEGRAM_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()
client = OpenAI(api_key=OPENAI_API_KEY)

RSS_FEEDS = [
    "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://rss.cnn.com/rss/edition.rss"
]

SENT_TITLES_FILE = "sent_titles.json"
MAX_POSTS = 5

def load_sent_titles():
    if not os.path.exists(SENT_TITLES_FILE):
        return []
    with open(SENT_TITLES_FILE, "r") as file:
        return json.load(file)

def save_sent_titles(titles):
    with open(SENT_TITLES_FILE, "w") as file:
        json.dump(titles, file)

def get_embedding(text):
    response = client.embeddings.create(model="text-embedding-ada-002", input=[text])
    return response.data[0].embedding

def get_summary(text):
    prompt = (
        f"Summarize the following news article into 7–10 concise sentences. "
        f"Do not include any links. Write in a professional tone for an American audience.\n\n{text}"
    )
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()

def extract_hashtags(title):
    return " ".join(f"#{word.strip('.,!?')" for word in title.split() if word.istitle() and len(word) > 3)

async def post_news():
    sent_titles = load_sent_titles()
    all_entries = []

    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        all_entries.extend(feed.entries)

    all_entries = sorted(all_entries, key=lambda e: e.get("published_parsed", datetime.min), reverse=True)

    count = 0
    for entry in all_entries:
        title = entry.get("title", "")
        summary = entry.get("summary", "")
        published = entry.get("published", "")
        source = entry.get("source", {}).get("title") or entry.get("publisher") or entry.get("feed", {}).get("title") or "Unknown Source"
        image = entry.get("media_content", [{}])[0].get("url", "")

        if title in sent_titles:
            continue

        full_text = f"{title}. {summary}"
        embedding = get_embedding(full_text)

        if is_duplicate(embedding):
            continue

        brief = get_summary(full_text)
        hashtags = extract_hashtags(title)
        published_date = datetime(*entry.published_parsed[:6]).strftime("%B %d, %Y")

        post = (
            f"<b>{title}</b>\n\n"
            f"{brief}\n\n"
            f"<i>Source:</i> {source}\n"
            f"<i>Published:</i> {published_date}\n"
            f"{hashtags}"
        )

        try:
            if image:
                await bot.send_photo(chat_id=CHANNEL_ID, photo=image, caption=post, parse_mode=ParseMode.HTML)
            else:
                await bot.send_message(chat_id=CHANNEL_ID, text=post, parse_mode=ParseMode.HTML)
            sent_titles.append(title)
            save_sent_titles(sent_titles)
            save_embedding(title, embedding)
            count += 1
            if count >= MAX_POSTS:
                break
        except Exception as e:
            print(f"Failed to send post: {e}")
            continue

if __name__ == "__main__":
    asyncio.run(post_news())
