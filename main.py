import os
import json
import time
import requests
import feedparser
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.utils import executor
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
NEWS_FEED_URL = "https://rss.nytimes.com/services/xml/rss/nyt/US.xml"

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()
client = OpenAI(api_key=OPENAI_API_KEY)

def load_sent_titles():
    try:
        with open("sent_titles.json", "r") as file:
            data = json.load(file)
            return data.get("titles", [])
    except FileNotFoundError:
        return []

def save_sent_title(title):
    titles = load_sent_titles()
    titles.append(title)
    with open("sent_titles.json", "w") as file:
        json.dump({"titles": titles}, file)

def generate_summary(text):
    prompt = f"Summarize the following news in 2-3 sentences in English:\n\n{text}"
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("OpenAI error:", e)
        return None

def create_post(title, summary):
    return f"<b>{title}</b>\n\n{summary}"

async def check_news():
    sent_titles = load_sent_titles()
    feed = feedparser.parse(NEWS_FEED_URL)

    # Вставляем тестовую новость
    test_entry = {
        "title": "Test News Title",
        "link": "https://example.com",
        "summary": "This is a test summary from the inserted article."
    }
    feed.entries.insert(0, test_entry)

    for entry in feed.entries:
        title = entry.title
        summary = entry.summary
        if title not in sent_titles:
            full_summary = generate_summary(summary)
            if full_summary:
                message = create_post(title, full_summary)
                try:
                    await bot.send_message(chat_id=CHANNEL_ID, text=message)
                    save_sent_title(title)
                    print(f"Posted: {title}")
                except Exception as e:
                    print("Telegram error:", e)
            else:
                print("Skipping due to OpenAI summary failure.")

@dp.message_handler(commands=["start"])
async def start_handler(message: types.Message):
    await message.answer("US News Radar is running!")

if __name__ == "__main__":
    from asyncio import run
    run(check_news())
