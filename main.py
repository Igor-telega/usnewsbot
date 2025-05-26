import asyncio
import os
import feedparser
import requests
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
SENT_TITLES_FILE = "sent_titles.json"

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
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
    sent_titles = load_sent_titles()
    new_titles = []

    for source, url in RSS_FEEDS.items():
        feed = feedparser.parse(url)
        count = 0
        for entry in feed.entries:
            if entry.title in sent_titles:
                continue
            summary = getattr(entry, 'summary', '') or getattr(entry, 'description', '')
            image_url = None
            if "media_content" in entry and entry.media_content:
                image_url = entry.media_content[0].get("url")

            summarized = await summarize_text(f"{entry.title}\n\n{summary}")
            if not summarized:
                print(f"Skipping: OpenAI returned no summary for '{entry.title}'")
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

            new_titles.append(entry.title)
            count += 1
            if count >= MAX_POSTS_PER_RUN:
                break

    save_sent_titles(sent_titles + new_titles)

async def main():
    while True:
        try:
            await fetch_and_send_news()
        except Exception as e:
            print(f"Error during news fetch: {e}")
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
