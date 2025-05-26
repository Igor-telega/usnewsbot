import os
import json
import asyncio
import logging
import feedparser
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

client = OpenAI(api_key=OPENAI_API_KEY)

RSS_URL = f"https://newsdata.io/api/1/news?apikey={NEWS_API_KEY}&country=us&language=en&category=top"

SENT_TITLES_FILE = "/data/sent_titles.json"

def load_sent_titles():
    if os.path.exists(SENT_TITLES_FILE):
        with open(SENT_TITLES_FILE, "r") as f:
            return json.load(f)["titles"]
    return []

def save_sent_titles(titles):
    with open(SENT_TITLES_FILE, "w") as f:
        json.dump({"titles": titles}, f)

async def fetch_news():
    feed = feedparser.parse(RSS_URL)
    sent_titles = load_sent_titles()
    new_titles = []

    for entry in feed.entries:
        title = entry.title.strip()
        summary = entry.summary.strip()
        link = entry.link.strip()

        if title in sent_titles:
            continue

        full_text = f"{title}\n\n{summary}"

        try:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a news editor. Summarize news in 4–5 informative sentences, keeping it engaging and factual. Do not include links."},
                    {"role": "user", "content": full_text}
                ],
                max_tokens=500,
                temperature=0.7
            )

            summary_text = response.choices[0].message.content.strip()

            caption = f"<b>{title}</b>\n\n{summary_text}"

            await bot.send_message(chat_id=CHANNEL_ID, text=caption)
            new_titles.append(title)

        except Exception as e:
            logging.exception("Error sending news:")
            continue

    save_sent_titles(sent_titles + new_titles)

async def main():
    while True:
        await fetch_news()
        await asyncio.sleep(600)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
