import os
import json
import requests
import feedparser
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.utils.markdown import hbold
from dotenv import load_dotenv
import asyncio

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

SENT_TITLES_FILE = "sent_titles.json"
FEED_URL = "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"

def load_sent_titles():
    if not os.path.exists(SENT_TITLES_FILE):
        return set()
    with open(SENT_TITLES_FILE, "r") as f:
        data = json.load(f)
        return set(data.get("titles", []))

def save_sent_titles(titles):
    with open(SENT_TITLES_FILE, "w") as f:
        json.dump({"titles": list(titles)}, f)

def extract_hashtags(text):
    hashtags = []
    lower_text = text.lower()
    if "trump" in lower_text:
        hashtags.append("#Trump")
    if "biden" in lower_text:
        hashtags.append("#Biden")
    if "ai" in lower_text:
        hashtags.append("#AI")
    if "senate" in lower_text or "congress" in lower_text:
        hashtags.append("#Politics")
    if "israel" in lower_text or "gaza" in lower_text or "putin" in lower_text or "ukraine" in lower_text:
        hashtags.append("#World")
    if "apple" in lower_text or "google" in lower_text:
        hashtags.append("#Tech")
    if "court" in lower_text or "judge" in lower_text:
        hashtags.append("#Justice")
    if "climate" in lower_text or "weather" in lower_text:
        hashtags.append("#Climate")
    return " ".join(hashtags[:3])

async def fetch_news():
    sent_titles = load_sent_titles()
    feed = feedparser.parse(FEED_URL)
    new_titles = set()

    for entry in feed.entries[:10]:
        title = entry.title.strip()
        if title in sent_titles:
            continue

        summary = entry.summary.strip()
        source = entry.get("source", {}).get("title", "NY Times")
        image_url = ""
        if "media_content" in entry:
            image_url = entry.media_content[0]["url"]

        hashtags = extract_hashtags(title + " " + summary)

        text = f"<b>{hbold(title)}</b>\n\n{summary}\n\n<i>{source}</i>\n{hashtags}"

        try:
            if image_url:
                await bot.send_photo(chat_id=CHANNEL_ID, photo=image_url, caption=text)
            else:
                await bot.send_message(chat_id=CHANNEL_ID, text=text)
            new_titles.add(title)
            await asyncio.sleep(3)
        except Exception as e:
            print(f"Error sending news: {e}")

    sent_titles.update(new_titles)
    save_sent_titles(sent_titles)

async def main():
    while True:
        await fetch_news()
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
