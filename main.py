import os
import json
import feedparser
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv
from embeddings_storage import is_duplicate, save_embedding
import openai

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=TELEGRAM_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
openai.api_key = OPENAI_API_KEY

SENT_TITLES_FILE = "sent_titles.json"
NEWS_FEEDS = [
    "http://rss.cnn.com/rss/edition.rss",
    "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://www.theguardian.com/world/rss"
]

MAX_NEWS_AGE_HOURS = 24

def load_sent_titles():
    if os.path.exists(SENT_TITLES_FILE):
        with open(SENT_TITLES_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_sent_titles(titles):
    with open(SENT_TITLES_FILE, "w") as f:
        json.dump(list(titles), f)

async def get_embedding(text):
    response = openai.Embedding.create(
        model="text-embedding-ada-002",
        input=text
    )
    return response["data"][0]["embedding"]

def is_recent(entry):
    if not hasattr(entry, "published_parsed"):
        return False
    published = datetime(*entry.published_parsed[:6])
    return datetime.utcnow() - published <= timedelta(hours=MAX_NEWS_AGE_HOURS)

async def send_news():
    sent_titles = load_sent_titles()

    for feed_url in NEWS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            title = entry.title
            if title in sent_titles or not is_recent(entry):
                continue

            description = entry.get("summary", "")
            link = entry.link
            published = datetime(*entry.published_parsed[:6]).strftime("%B %d, %Y")
            source = feed.feed.get("title", "News Source")

            full_text = f"{title}\n\n{description}"
            embedding = await get_embedding(full_text)

            if is_duplicate(embedding):
                continue

            save_embedding(title, embedding)

            hashtags = "#" + " #".join([
                word.strip(".,!?").capitalize()
                for word in title.split()
                if word.isalpha() and len(word) > 3
            ][:3])

            message = (
                f"<b>{title}</b>\n\n"
                f"{description}\n"
                f"<i>Source:</i> <a href=\"{link}\">{source}</a>\n\n"
                f"🕓 <i>Published:</i> {published}\n"
                f"{hashtags}"
            )

            await bot.send_message(chat_id=CHANNEL_ID, text=message, disable_web_page_preview=False)
            sent_titles.add(title)

    save_sent_titles(sent_titles)

async def main():
    while True:
        try:
            await send_news()
        except Exception as e:
            print(f"Error: {e}")
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
