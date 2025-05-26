import os
import json
import logging
import requests
import feedparser
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.utils.markdown import hbold
from dotenv import load_dotenv
import openai

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

openai.api_key = OPENAI_API_KEY

NEWS_FEEDS = [
    "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "http://feeds.bbci.co.uk/news/rss.xml",
    "http://rss.cnn.com/rss/edition.rss",
    "https://feeds.a.dj.com/rss/RSSWorldNews.xml",
    "http://feeds.reuters.com/reuters/topNews",
    "https://www.theguardian.com/world/rss",
    "https://www.npr.org/rss/rss.php?id=1001",
    "https://apnews.com/rss"
]

MAX_NEWS_PER_POST = 5

def load_sent_titles():
    try:
        with open("sent_titles.json", "r") as f:
            return set(json.load(f)["titles"])
    except (FileNotFoundError, json.JSONDecodeError):
        return set()

def save_sent_titles(titles):
    with open("sent_titles.json", "w") as f:
        json.dump({"titles": list(titles)}, f)

async def summarize_text(text):
    prompt = f"Summarize this news article in 2–4 sentences as a news brief for Telegram:\n\n{text[:3000]}"
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=350,
        )
        return response["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logging.error(f"OpenAI error: {e}")
        return None

async def fetch_news():
    sent_titles = load_sent_titles()
    new_titles = set()
    posts_sent = 0

    for url in NEWS_FEEDS:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            title = entry.title
            if title in sent_titles:
                continue
            link = entry.link
            summary = entry.get("summary", "")
            full_text = f"{title}. {summary}"
            shortened = await summarize_text(full_text)
            if not shortened:
                continue

            hashtags = " ".join([f"#{tag.strip().replace(' ', '')}" for tag in entry.get("tags", [])[:3]]) if entry.get("tags") else ""

            message = f"<b>{hbold(title)}</b>\n\n{shortened}\n\n<i>{entry.get('source', {}).get('title', 'News')}</i>\n{hashtags}"
            try:
                await bot.send_message(chat_id=CHANNEL_ID, text=message)
                new_titles.add(title)
                posts_sent += 1
                if posts_sent >= MAX_NEWS_PER_POST:
                    break
            except Exception as e:
                logging.error(f"Failed to send message: {e}")
        if posts_sent >= MAX_NEWS_PER_POST:
            break

    sent_titles.update(new_titles)
    save_sent_titles(sent_titles)

async def main():
    while True:
        await fetch_news()
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
