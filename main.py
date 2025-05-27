import os
import json
import feedparser
import requests
import numpy as np
from datetime import datetime, timedelta
from dotenv import load_dotenv
from aiogram import Bot, types
from aiogram.enums import ParseMode
from embeddings_storage import is_duplicate, save_embedding

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=TELEGRAM_TOKEN, parse_mode=ParseMode.HTML)

sent_titles_file = "sent_titles.json"
MAX_NEWS = 5

def load_sent_titles():
    if os.path.exists(sent_titles_file):
        with open(sent_titles_file, "r") as f:
            return json.load(f)
    return []

def save_sent_titles(titles):
    with open(sent_titles_file, "w") as f:
        json.dump(titles, f)

def get_embedding(text):
    url = "https://api.openai.com/v1/embeddings"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "text-embedding-ada-002",
        "input": text
    }
    response = requests.post(url, headers=headers, json=data)
    return response.json()["data"][0]["embedding"]

def summarize(text):
    prompt = f"Summarize the news article below in 2-3 short, clear sentences:\n\n{text}"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }
    response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data)
    return response.json()["choices"][0]["message"]["content"]

def format_tags(title):
    words = [word for word in title.split() if word.istitle() and word.isalpha()]
    return " ".join(f"#{word}" for word in words[:5])

def extract_date(entry):
    try:
        return datetime(*entry.published_parsed[:6])
    except Exception:
        return datetime.utcnow()

async def send_news():
    sent_titles = load_sent_titles()
    urls = [
        "https://rss.nytimes.com/services/xml/rss/nyt/US.xml",
        "https://feeds.bbci.co.uk/news/rss.xml",
        "https://rss.cnn.com/rss/edition.rss"
    ]
    count = 0
    for url in urls:
        if count >= MAX_NEWS:
            break
        feed = feedparser.parse(url)
        for entry in feed.entries:
            if count >= MAX_NEWS:
                break
            title = entry.title
            if title in sent_titles:
                continue

            published_date = extract_date(entry)
            if datetime.utcnow() - published_date > timedelta(hours=24):
                continue

            embedding = get_embedding(title)
            if is_duplicate(embedding):
                continue

            text = entry.get("summary", "")
            summary = summarize(text)
            image_url = ""
            if "media_content" in entry:
                image_url = entry.media_content[0]["url"]
            elif "media_thumbnail" in entry:
                image_url = entry.media_thumbnail[0]["url"]

            source = feed.feed.get("title", "News").split()[0]
            published = published_date.strftime("%B %d, %Y")
            tags = format_tags(title)

            message = f"<b>{title}</b>\n\n{summary}\n\n<em>Source:</em> {source}\n<em>Published:</em> {published}\n{tags}"
            if image_url:
                try:
                    await bot.send_photo(chat_id=CHANNEL_ID, photo=image_url, caption=message)
                except Exception:
                    await bot.send_message(chat_id=CHANNEL_ID, text=message)
            else:
                await bot.send_message(chat_id=CHANNEL_ID, text=message)

            sent_titles.append(title)
            save_embedding(title, embedding)
            count += 1

    save_sent_titles(sent_titles)

import asyncio
if __name__ == "__main__":
    asyncio.run(send_news())
