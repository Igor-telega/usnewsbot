import os
import json
import time
import logging
import requests
import feedparser
from aiogram import Bot, Dispatcher, types
from aiogram.utils.markdown import hbold
from aiogram.types import InputFile
from aiogram.enums import ParseMode
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID")

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()
client = OpenAI(api_key=OPENAI_API_KEY)

RSS_FEEDS = {
    "NYT": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "CNN": "http://rss.cnn.com/rss/edition.rss",
    "Reuters": "http://feeds.reuters.com/reuters/topNews",
    "AP": "https://rss.apnews.com/apf-topnews",
    "NPR": "https://feeds.npr.org/1001/rss.xml",
    "Guardian": "https://www.theguardian.com/world/rss"
}

HASHTAG_MAP = {
    "politics": "#Politics",
    "trump": "#Trump",
    "biden": "#Biden",
    "ukraine": "#Ukraine",
    "israel": "#Israel",
    "gaza": "#Gaza",
    "china": "#China",
    "russia": "#Russia",
    "election": "#Elections",
    "ai": "#AI",
    "world": "#World",
    "book": "#Books",
    "summer": "#Lifestyle"
}

def load_sent_titles():
    try:
        with open("sent_titles.json", "r") as f:
            return json.load(f)["titles"]
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_sent_titles(titles):
    with open("sent_titles.json", "w") as f:
        json.dump({"titles": titles[-50:]}, f, indent=2)

def generate_hashtags(title):
    hashtags = []
    lowered = title.lower()
    for keyword, tag in HASHTAG_MAP.items():
        if keyword in lowered:
            hashtags.append(tag)
    return " ".join(hashtags)

def fetch_image(entry):
    try:
        if "media_content" in entry:
            return entry.media_content[0]["url"]
        elif "media_thumbnail" in entry:
            return entry.media_thumbnail[0]["url"]
        elif "links" in entry:
            for link in entry.links:
                if link["type"].startswith("image"):
                    return link["href"]
    except Exception:
        return None
    return None

def summarize(text):
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        temperature=0.6,
        messages=[
            {"role": "system", "content": "You summarize news articles in 2–4 sentences for Telegram."},
            {"role": "user", "content": f"Summarize this news article in 2–4 sentences as a news brief for Telegram:\n\n{text}"}
        ]
    )
    return response.choices[0].message.content.strip()

async def post_news():
    sent_titles = load_sent_titles()
    posted = 0

    for source, url in RSS_FEEDS.items():
        if posted >= 5:
            break

        feed = feedparser.parse(url)

        for entry in feed.entries:
            title = entry.title.strip()
            if title in sent_titles:
                continue

            summary_text = summarize(entry.title + "\n\n" + entry.get("summary", ""))
            image_url = fetch_image(entry)
            hashtags = generate_hashtags(title)
            source_name = f"<i>{source} > Top Stories</i>"

            caption = f"<b>{title}</b>\n\n{summary_text}\n\n{source_name}"
            if hashtags:
                caption += f"\n{hashtags}"

            if image_url:
                try:
                    img_data = requests.get(image_url, timeout=5).content
                    with open("temp.jpg", "wb") as f:
                        f.write(img_data)
                    photo = InputFile("temp.jpg")
                    await bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=caption)
                    os.remove("temp.jpg")
                except Exception as e:
                    logging.warning(f"Image failed: {e}")
                    await bot.send_message(chat_id=CHANNEL_ID, text=caption)
            else:
                await bot.send_message(chat_id=CHANNEL_ID, text=caption)

            sent_titles.append(title)
            posted += 1
            if posted >= 5:
                break

    save_sent_titles(sent_titles)

async def main_loop():
    while True:
        try:
            await post_news()
        except Exception as e:
            logging.error(f"Main loop error: {e}")
        await asyncio.sleep(60)  # Every 60 seconds

if __name__ == "__main__":
    import asyncio
    asyncio.run(main_loop())
