import asyncio
import os
import feedparser
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.types import InputFile
from aiogram.enums import ParseMode
from dotenv import load_dotenv
from datetime import datetime
import json
import openai

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

RSS_FEEDS = {
    "NYT": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "CNN": "http://rss.cnn.com/rss/cnn_topstories.rss",
    "Reuters": "http://feeds.reuters.com/reuters/topNews",
    "AP": "https://apnews.com/rss",
    "The Guardian": "https://www.theguardian.com/world/rss"
}

MAX_POSTS_PER_RUN = 5
SENT_TITLES_FILE = "sent_titles.json"

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

def load_sent_titles():
    if not os.path.exists(SENT_TITLES_FILE):
        return []
    with open(SENT_TITLES_FILE, "r") as file:
        data = json.load(file)
        return data.get("titles", [])

def save_sent_titles(titles):
    with open(SENT_TITLES_FILE, "w") as file:
        json.dump({"titles": titles}, file)

async def summarize_text(text):
    if not text.strip():
        print("Empty article text, skipping summarization.")
        return None
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a news assistant."},
                {"role": "user", "content": f"Summarize this news article in 2-4 sentences as a news brief for Telegram:\n{text}"}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"OpenAI summarization error: {e}")
        return None

async def fetch_and_send_news():
    print("Fetching RSS feeds...")
    sent_titles = load_sent_titles()
    new_titles = []
    total_processed = 0

    for source, url in RSS_FEEDS.items():
        print(f"Parsing feed: {source}")
        feed = feedparser.parse(url)
        count = 0
        print(f"Found {len(feed.entries)} entries in {source}")

        for entry in feed.entries:
            if count >= MAX_POSTS_PER_RUN:
                break
            total_processed += 1

            if entry.title in sent_titles:
                print(f"- Skipping already sent: {entry.title}")
                continue

            summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
            if not summary:
                print(f"- Skipping: no summary or description for '{entry.title}'")
                continue

            summarized = await summarize_text(f"{entry.title}\n{summary}")
            if not summarized:
                print(f"- Skipping: OpenAI returned no summary for '{entry.title}'")
                continue

            message = f"<b>{entry.title}</b>\n\n{summarized}\n\n<i>{source}</i>\n#AI #World"

            image_url = None
            if "media_content" in entry and entry.media_content:
                image_url = entry.media_content[0].get("url")

            try:
                if image_url:
                    image_data = requests.get(image_url).content
                    with open("temp.jpg", "wb") as f:
                        f.write(image_data)
                    photo = InputFile("temp.jpg")
                    await bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=message, parse_mode=ParseMode.HTML)
                    os.remove("temp.jpg")
                    print(f"+ Sent with image: {entry.title}")
                else:
                    await bot.send_message(chat_id=CHANNEL_ID, text=message, parse_mode=ParseMode.HTML)
                    print(f"+ Sent without image: {entry.title}")
            except Exception as e:
                print(f"Error sending message: {e}")

            new_titles.append(entry.title)
            count += 1

    print(f"Finished. Total processed entries: {total_processed}, sent: {len(new_titles)}.")
    save_sent_titles(sent_titles + new_titles)

async def main():
    while True:
        try:
            await fetch_and_send_news()
        except Exception as e:
            print(f"Error during fetch/send loop: {e}")
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
