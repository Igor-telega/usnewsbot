import os
import json
import asyncio
import logging
import feedparser
import aiohttp
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.enums.parse_mode import ParseMode
from aiogram.utils.markdown import hbold
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

NEWS_SOURCES = [
    "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "http://rss.cnn.com/rss/cnn_topstories.rss",
    "http://feeds.reuters.com/reuters/topNews",
    "https://feeds.npr.org/1001/rss.xml",
    "https://www.theguardian.com/world/rss"
]

TAGS = {
    "Trump": "#Trump",
    "Biden": "#Biden",
    "Ukraine": "#Ukraine",
    "Russia": "#Russia",
    "Israel": "#Israel",
    "Palestine": "#Palestine",
    "AI": "#AI",
    "World": "#World",
    "Justice": "#Justice",
    "Politics": "#Politics",
}

openai = AsyncOpenAI(api_key=OPENAI_API_KEY)

async def summarize_text(text):
    try:
        response = await openai.chat.completions.create(
            model="gpt-4",
            messages=[{
                "role": "user",
                "content": f"Summarize this news article in 2-4 sentences as a news brief for Telegram:\n\n{text}"
            }],
            temperature=0.7,
            max_tokens=300
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"OpenAI error: {e}")
        return None

def extract_tags(title):
    return " ".join(tag for word, tag in TAGS.items() if word.lower() in title.lower())

async def fetch_and_send_news():
    try:
        with open("sent_titles.json", "r") as f:
            sent_titles = json.load(f)["titles"]
    except (FileNotFoundError, json.JSONDecodeError):
        sent_titles = []

    all_entries = []
    for url in NEWS_SOURCES:
        parsed_feed = feedparser.parse(url)
        all_entries.extend(parsed_feed.entries)

    new_entries = [entry for entry in all_entries if entry.title not in sent_titles][:5]

    async with aiohttp.ClientSession() as session:
        for entry in new_entries:
            title = entry.title
            link = entry.link
            source = entry.get("source", {}).get("title", entry.get("publisher", ""))
            content = entry.get("summary", "") or entry.get("description", "")

            summary = await summarize_text(content)
            if not summary:
                continue

            caption = f"<b>{title}</b>\n\n{summary}\n\n<i>{source or 'News Source'}</i>\n{extract_tags(title)}"
            image_url = (
                entry.get("media_content", [{}])[0].get("url")
                or entry.get("media_thumbnail", [{}])[0].get("url")
                or None
            )

            try:
                if image_url:
                    async with session.get(image_url) as img_resp:
                        if img_resp.status == 200:
                            img_data = await img_resp.read()
                            photo = types.InputFile.from_buffer(img_data, filename="image.jpg")
                            await bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=caption)
                        else:
                            await bot.send_message(chat_id=CHANNEL_ID, text=caption)
                else:
                    await bot.send_message(chat_id=CHANNEL_ID, text=caption)
            except Exception as e:
                logging.warning(f"Failed to send message with image: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text=caption)

            sent_titles.append(title)

        with open("sent_titles.json", "w") as f:
            json.dump({"titles": sent_titles}, f)

async def main():
    while True:
        await fetch_and_send_news()
        await asyncio.sleep(3600)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
