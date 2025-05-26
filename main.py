import asyncio
import os
import feedparser
import requests
import hashlib
from aiogram import Bot, Dispatcher
from aiogram.types import FSInputFile
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv
from datetime import datetime
from openai import OpenAI
import json

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

RSS_FEEDS = {
    "NYT": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "CNN": "http://rss.cnn.com/rss/cnn_topstories.rss",
    "Reuters": "http://feeds.reuters.com/reuters/topNews",
    "AP": "https://apnews.com/rss",
    "The Guardian": "https://www.theguardian.com/world/rss"
}

MAX_POSTS_PER_RUN = 5
HASHES_FILE = "sent_hashes.json"

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

def load_sent_hashes():
    if not os.path.exists(HASHES_FILE):
        return set()
    with open(HASHES_FILE, "r") as file:
        return set(json.load(file))

def save_sent_hashes(hashes):
    with open(HASHES_FILE, "w") as file:
        json.dump(list(hashes), file)

def make_news_hash(title, summary):
    content = (title + summary).strip().lower().encode("utf-8")
    return hashlib.sha256(content).hexdigest()

async def summarize_text(text):
    try:
        chat_response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a news summarizer. Write in English, 3-5 sentences, informative, as if for a news feed. Don't just say what the article is about — tell the story."},
                {"role": "user", "content": text}
            ]
        )
        return chat_response.choices[0].message.content.strip()
    except Exception as e:
        print("OpenAI summarization error:", e)
        return None

async def fetch_and_send_news():
    sent_hashes = load_sent_hashes()
    new_hashes = set()
    posts_sent = 0

    for source, url in RSS_FEEDS.items():
        if posts_sent >= MAX_POSTS_PER_RUN:
            break
        feed = feedparser.parse(url)

        for entry in feed.entries:
            summary = getattr(entry, 'summary', '') or getattr(entry, 'description', '')
            news_hash = make_news_hash(entry.title, summary)

            if news_hash in sent_hashes or news_hash in new_hashes:
                continue

            image_url = None
            if "media_content" in entry and entry.media_content:
                image_url = entry.media_content[0].get("url")

            summarized = await summarize_text(f"{entry.title}\n\n{summary}")
            if not summarized:
                continue

            message = f"<b>{entry.title}</b>\n\n{summarized}\n\n<i>{source}</i>\n#AI #World"

            try:
                if image_url:
                    image_data = requests.get(image_url).content
                    with open("temp.jpg", "wb") as f:
                        f.write(image_data)
                    photo = FSInputFile("temp.jpg")
                    await bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=message)
                    os.remove("temp.jpg")
                else:
                    await bot.send_message(chat_id=CHANNEL_ID, text=message)
            except Exception as e:
                print(f"Error sending message: {e}")

            new_hashes.add(news_hash)
            posts_sent += 1

            if posts_sent >= MAX_POSTS_PER_RUN:
                break

    save_sent_hashes(sent_hashes.union(new_hashes))

async def main():
    while True:
        try:
            await fetch_and_send_news()
        except Exception as e:
            print(f"Error during news fetch: {e}")
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
