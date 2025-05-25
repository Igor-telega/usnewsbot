import json
import os
import requests
import feedparser
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import InputFile
from openai import OpenAI

TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()
client = OpenAI(api_key=OPENAI_API_KEY)

NEWS_URL = f"https://newsapi.org/v2/top-headlines?country=us&apiKey={NEWS_API_KEY}"
SENT_TITLES_FILE = "sent_titles.json"

def load_sent_titles():
    try:
        with open(SENT_TITLES_FILE, "r") as file:
            return set(json.load(file)["titles"])
    except (FileNotFoundError, json.JSONDecodeError):
        return set()

def save_sent_titles(titles):
    with open(SENT_TITLES_FILE, "w") as file:
        json.dump({"titles": list(titles)}, file)

def get_news():
    response = requests.get(NEWS_URL)
    articles = response.json().get("articles", [])
    return [{"title": article["title"], "url": article["url"]} for article in articles]

def generate_summary(title):
    prompt = f"Summarize the following news in one short sentence:\n\n{title}"
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=60
    )
    return response.choices[0].message.content.strip()

async def send_news():
    sent_titles = load_sent_titles()
    news_items = get_news()

    for item in news_items:
        title = item["title"]
        url = item["url"]

        if title in sent_titles:
            continue

        summary = generate_summary(title)
        message = f"{title}\n\n{summary}\n\nПодробнее: {url}"

        try:
            await bot.send_message(chat_id=CHANNEL_ID, text=message)
            sent_titles.add(title)
            save_sent_titles(sent_titles)
            await asyncio.sleep(2)
        except Exception as e:
            logging.error(f"Failed to send message: {e}")

if __name__ == "__main__":
    asyncio.run(send_news())
