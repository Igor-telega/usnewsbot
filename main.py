import os
import json
import asyncio
import logging
from datetime import datetime, timedelta

import feedparser
from openai import OpenAI
from aiogram import Bot, Dispatcher, types
from aiogram.enums.parse_mode import ParseMode
from dotenv import load_dotenv

from image_gen import generate_image
from embeddings import get_embedding, is_duplicate, save_embedding

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")  # строка, не int
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

openai = OpenAI(api_key=OPENAI_API_KEY)

news_feeds = {
    "NYT": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "CNN": "http://rss.cnn.com/rss/edition.rss",
    "BBC": "http://feeds.bbci.co.uk/news/rss.xml"
}

sent_titles_file = "sent_titles.json"
try:
    with open(sent_titles_file, "r") as f:
        sent_titles = json.load(f)
except FileNotFoundError:
    sent_titles = []

def fetch_feed(url):
    return feedparser.parse(url)

def is_recent(entry, days=1):
    published = entry.get("published_parsed")
    if not published:
        return False
    pub_date = datetime(*published[:6])
    return datetime.utcnow() - pub_date < timedelta(days=days)

async def summarize(title, description, source):
    prompt = (
        f"Summarize the following news article from {source} in up to 10 short journalistic sentences. "
        f"Do not repeat the title. Keep it neutral and informative. "
        f"Title: {title}\n"
        f"Description: {description}"
    )
    response = await openai.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a news editor."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content.strip()

def extract_tags(text, limit=5):
    words = text.split()
    tags = [f"#{word.strip('.').capitalize()}" for word in words if word.istitle()]
    return tags[:limit]

async def post_to_telegram(text, image_url=None):
    if image_url:
        await bot.send_photo(CHANNEL_ID, photo=image_url, caption=text)
    else:
        await bot.send_message(CHANNEL_ID, text)

async def process_news():
    collected = []
    max_news = 5
    recent_news = {source: [entry for entry in fetch_feed(url).entries if is_recent(entry)] for source, url in news_feeds.items()}
    for i in range(max_news):
        for source, entries in recent_news.items():
            if i < len(entries):
                entry = entries[i]
                if entry.title in sent_titles:
                    continue
                summary = await summarize(entry.title, entry.get("summary", ""), source)
                tags = extract_tags(entry.title + " " + summary)
                published_time = datetime(*entry.published_parsed[:6]).strftime("%a, %d %b %Y %H:%M:%S %Z")
                source_line = f"\n\nSource: {source}\nPublished: {published_time}"
                tag_line = "\n" + " ".join(tags) if tags else ""
                full_post = summary + source_line + tag_line

                embedding = get_embedding(entry.title)
                if not is_duplicate(embedding, [get_embedding(title) for title in sent_titles]):
                    image_url = entry.get("media_content", [{}])[0].get("url") if "media_content" in entry else None
                    if not image_url:
                        image_url = generate_image(entry.title)
                    await post_to_telegram(full_post, image_url)
                    sent_titles.append(entry.title)
                    save_embedding(entry.title, embedding)
                    with open(sent_titles_file, "w") as f:
                        json.dump(sent_titles, f)
                if len(collected) >= max_news:
                    return

async def main():
    await process_news()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
