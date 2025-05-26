import os
import json
import asyncio
import feedparser
import logging
from datetime import datetime
from openai import AsyncOpenAI
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.utils.markdown import hbold
from aiogram.types import InputFile
from python_dotenv import load_dotenv
import aiohttp

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# RSS источники
FEEDS = [
    "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "http://feeds.bbci.co.uk/news/rss.xml",
    "https://www.cnn.com/rss/edition.rss",
    "https://feeds.npr.org/1001/rss.xml",
    "https://www.reutersagency.com/feed/?best-topics=politics&r=US&post_type=best",
    "https://www.theguardian.com/world/rss",
]

async def summarize_text(article_text):
    try:
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "Summarize this news article in 2–4 sentences as a Telegram post with a bold headline, short readable text, source name in italics, and relevant hashtags at the end."
                },
                {"role": "user", "content": article_text}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"OpenAI error: {e}")
        return None

def load_sent_titles():
    if os.path.exists("sent_titles.json"):
        with open("sent_titles.json", "r") as f:
            return json.load(f).get("titles", [])
    return []

def save_sent_titles(titles):
    with open("sent_titles.json", "w") as f:
        json.dump({"titles": titles}, f)

async def fetch_image(session, url):
    try:
        async with session.get(url) as response:
            if response.status == 200:
                return await response.read()
    except Exception as e:
        logging.warning(f"Image fetch failed: {e}")
    return None

async def fetch_and_send_news():
    sent_titles = load_sent_titles()
    new_titles = []
    session = aiohttp.ClientSession()
    sent_count = 0

    try:
        for feed_url in FEEDS:
            if sent_count >= 5:
                break

            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                if entry.title in sent_titles:
                    continue

                summary = await summarize_text(entry.get("summary", entry.get("description", "")))
                if not summary:
                    continue

                # Получаем изображение
                image_url = None
                if "media_content" in entry and entry.media_content:
                    image_url = entry.media_content[0].get("url")
                elif "links" in entry:
                    for link in entry.links:
                        if link.get("type", "").startswith("image"):
                            image_url = link.get("href")
                            break

                text = summary

                try:
                    if image_url:
                        image_data = await fetch_image(session, image_url)
                        if image_data:
                            photo = types.BufferedInputFile(image_data, filename="image.jpg")
                            await bot.send_photo(CHANNEL_ID, photo=photo, caption=text)
                        else:
                            await bot.send_message(CHANNEL_ID, text)
                    else:
                        await bot.send_message(CHANNEL_ID, text)
                except Exception as e:
                    logging.warning(f"Failed to send message: {e}")
                    await bot.send_message(CHANNEL_ID, text)

                new_titles.append(entry.title)
                sent_count += 1

                if sent_count >= 5:
                    break
    finally:
        await session.close()
        save_sent_titles(sent_titles + new_titles)

async def main():
    while True:
        try:
            await fetch_and_send_news()
        except Exception as e:
            logging.error(f"Error in main loop: {e}")
        await asyncio.sleep(60)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
