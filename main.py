import json
import time
import requests
import feedparser
import openai
import asyncio
from telegram import Bot
from telegram.error import TelegramError
from PIL import Image
from io import BytesIO

import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

openai.api_key = OPENAI_API_KEY

RSS_FEEDS = [
    "http://feeds.bbci.co.uk/news/rss.xml",
    "https://rss.cnn.com/rss/edition.rss",
    "https://feeds.a.dj.com/rss/RSSWorldNews.xml",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"
]

SENT_TITLES_FILE = "sent_titles.json"

def load_sent_titles():
    try:
        with open(SENT_TITLES_FILE, "r") as f:
            return json.load(f)["titles"]
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_sent_titles(titles):
    with open(SENT_TITLES_FILE, "w") as f:
        json.dump({"titles": titles}, f)

async def send_news():
    bot = Bot(token=BOT_TOKEN)
    sent_titles = load_sent_titles()

    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        for entry in feed.entries[:3]:
            title = entry.title
            link = entry.link
            summary = entry.get("summary", "")

            if title in sent_titles:
                continue

            short_summary = generate_summary(title, summary)
            image_url = extract_image(entry)

            caption = f"{title}\n\n{short_summary}"

            try:
                if image_url:
                    image = download_image(image_url)
                    bot.send_photo(chat_id=CHANNEL_ID, photo=image, caption=caption)
                else:
                    bot.send_message(chat_id=CHANNEL_ID, text=caption)
                sent_titles.append(title)
                save_sent_titles(sent_titles)
                time.sleep(5)
            except TelegramError as e:
                print(f"Telegram error: {e}")
                continue

def generate_summary(title, text):
    prompt = f"Summarize the following news story in one clear sentence:\nTitle: {title}\nText: {text}"
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=60
        )
        return response["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print("OpenAI error:", e)
        return text

def extract_image(entry):
    media = entry.get("media_content", [])
    if media:
        return media[0].get("url")
    if "image" in entry:
        return entry.image.get("href")
    return None

def download_image(url):
    response = requests.get(url)
    if response.status_code == 200:
        return BytesIO(response.content)
    return None

if __name__ == "__main__":
    asyncio.run(send_news())
