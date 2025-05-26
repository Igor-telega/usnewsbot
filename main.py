import os
import json
import asyncio
import feedparser
import requests
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.types import BufferedInputFile
from openai import AsyncOpenAI

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=BOT_TOKEN, parse_mode=types.ParseMode.HTML)
dp = Dispatcher()

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

NEWS_SOURCES = {
    "NYT": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "CNN": "http://rss.cnn.com/rss/cnn_topstories.rss",
    "Reuters": "http://feeds.reuters.com/reuters/topNews",
    "AP": "https://apnews.com/rss",
    "NPR": "https://feeds.npr.org/1001/rss.xml",
    "Guardian": "https://www.theguardian.com/world/rss"
}

MAX_POSTS = 5
TITLES_FILE = "sent_titles.json"

def load_sent_titles():
    if not os.path.exists(TITLES_FILE):
        return []
    with open(TITLES_FILE, "r") as f:
        data = json.load(f)
    return data.get("titles", [])

def save_sent_titles(titles):
    with open(TITLES_FILE, "w") as f:
        json.dump({"titles": titles}, f)

async def summarize_text(text):
    try:
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "user",
                    "content": f"Summarize this news article in 2-4 sentences as a news brief for Telegram:\n\n{text}"
                }
            ],
            max_tokens=300
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("OpenAI error:", e)
        return None

async def fetch_and_send_news():
    sent_titles = load_sent_titles()
    new_titles = []

    for source, url in NEWS_SOURCES.items():
        feed = feedparser.parse(url)
        count = 0
        for entry in feed.entries:
            if entry.title in sent_titles or count >= MAX_POSTS:
                continue

            summary = await summarize_text(entry.summary if "summary" in entry else entry.description)
            if not summary:
                continue

            hashtags = " ".join([f"#{tag.term.replace(' ', '')}" for tag in entry.tags]) if "tags" in entry else ""
            caption = f"<b>{entry.title}</b>\n\n{summary}\n\n<i>{source}</i>\n{hashtags}"

            image_url = entry.media_content[0]['url'] if 'media_content' in entry else None

            try:
                if image_url:
                    img_data = requests.get(image_url).content
                    photo = BufferedInputFile(img_data, filename="image.jpg")
                    await bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=caption)
                else:
                    await bot.send_message(chat_id=CHANNEL_ID, text=caption)
                print(f"Posted: {entry.title}")
                new_titles.append(entry.title)
                count += 1
            except Exception as e:
                print("Failed to send message with image:", e)
                continue

    sent_titles.extend(new_titles)
    save_sent_titles(sent_titles)

async def main():
    while True:
        await fetch_and_send_news()
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
