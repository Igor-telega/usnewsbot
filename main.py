import os
import time
import asyncio
import logging
import requests
import feedparser
from datetime import datetime, timedelta
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode

from embeddings_storage import is_duplicate, save_embedding
from openai import OpenAI
from openai import OpenAIError

load_dotenv()
logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_TOKEN or not CHANNEL_ID or not OPENAI_API_KEY:
    raise ValueError("Missing TELEGRAM_TOKEN, CHANNEL_ID, or OPENAI_API_KEY in .env")

bot = Bot(token=TELEGRAM_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()
client = OpenAI(api_key=OPENAI_API_KEY)

NEWS_SOURCES = [
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "http://feeds.bbci.co.uk/news/world/rss.xml",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://rss.cnn.com/rss/edition_world.rss",
    "https://feeds.a.dj.com/rss/RSSWorldNews.xml",
    "https://www.theguardian.com/world/rss",
]

sent_titles = set()
MAX_ARTICLES = 30
MAX_AGE_HOURS = 24

def fetch_articles():
    articles = []
    for url in NEWS_SOURCES:
        feed = feedparser.parse(url)
        for entry in feed.entries[:MAX_ARTICLES]:
            title = entry.get("title", "")
            link = entry.get("link", "")
            published = entry.get("published", "")
            try:
                published_time = datetime(*entry.published_parsed[:6])
            except Exception:
                published_time = datetime.utcnow()
            if datetime.utcnow() - published_time > timedelta(hours=MAX_AGE_HOURS):
                continue
            articles.append({
                "title": title.strip(),
                "link": link,
                "published": published_time,
                "source": feed.feed.get("title", "Unknown Source")
            })
    return articles

def generate_summary(title, link):
    try:
        article = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a news editor."},
                {"role": "user", "content": f"Summarize this news for Telegram in 3-4 sentences in English. Add 3 relevant hashtags below. Link: {link}"}
            ]
        )
        return article.choices[0].message.content.strip()
    except OpenAIError as e:
        logging.error(f"OpenAI error: {e}")
        return ""

def get_embedding(text):
    try:
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=[text]
        )
        return response.data[0].embedding
    except OpenAIError as e:
        logging.error(f"Embedding error: {e}")
        return []

async def post_to_channel(article):
    embedding = get_embedding(article["title"])
    if not embedding or is_duplicate(embedding):
        return

    summary = generate_summary(article["title"], article["link"])
    if not summary:
        return

    msg = f"<b>{article['title']}</b>\n\n{summary}\n\nSource: {article['link']}\n\n" \
          f"🕒 Published: {article['published'].strftime('%B %d, %Y')}\n<i>{article['source']}</i>"
    await bot.send_message(CHANNEL_ID, msg)
    save_embedding(article["title"], embedding)

async def main():
    while True:
        try:
            articles = fetch_articles()
            for article in articles:
                if article["title"] in sent_titles:
                    continue
                await post_to_channel(article)
                sent_titles.add(article["title"])
                await asyncio.sleep(5)
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
        await asyncio.sleep(1800)

if __name__ == "__main__":
    asyncio.run(main())
