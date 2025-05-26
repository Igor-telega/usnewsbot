import os
import logging
import asyncio
import requests
import json
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.types.input_file import FSInputFile
from openai import OpenAI
from feedparser import parse
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

client = OpenAI(api_key=OPENAI_API_KEY)

SOURCES = [
    "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "http://rss.cnn.com/rss/edition.rss",
    "http://feeds.reuters.com/reuters/topNews",
    "https://www.npr.org/rss/rss.php?id=1001",
    "https://www.theguardian.com/world/rss"
]

TITLES_FILE = "sent_titles.json"

def load_sent_titles():
    if os.path.exists(TITLES_FILE):
        with open(TITLES_FILE, "r") as f:
            return json.load(f).get("titles", [])
    return []

def save_sent_titles(titles):
    with open(TITLES_FILE, "w") as f:
        json.dump({"titles": titles}, f)

def get_articles():
    articles = []
    for source in SOURCES:
        feed = parse(source)
        for entry in feed.entries:
            title = entry.title
            summary = entry.summary if hasattr(entry, "summary") else ""
            link = entry.link
            image = ""
            if "media_content" in entry:
                image = entry.media_content[0]["url"]
            elif "media_thumbnail" in entry:
                image = entry.media_thumbnail[0]["url"]
            articles.append({
                "title": title,
                "summary": summary,
                "link": link,
                "image": image,
                "source": feed.feed.title
            })
    return articles

def extract_hashtags(text):
    hashtags = []
    if "Trump" in text:
        hashtags.append("#Trump")
    if "AI" in text or "artificial intelligence" in text:
        hashtags.append("#AI")
    if "World" in text or "Ukraine" in text or "Gaza" in text:
        hashtags.append("#World")
    if "Justice" in text or "court" in text:
        hashtags.append("#Justice")
    return " ".join(hashtags)

async def summarize_text(text):
    prompt = f"Summarize this news article in 2–4 sentences as a news brief for Telegram:\n\n{text[:3000]}"
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=350,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"OpenAI error: {e}")
        return None

async def send_news():
    sent_titles = load_sent_titles()
    articles = get_articles()
    new_articles = [a for a in articles if a["title"] not in sent_titles][:5]

    for article in new_articles:
        summary = await summarize_text(article["summary"])
        if not summary:
            continue

        hashtags = extract_hashtags(article["title"] + " " + summary)
        caption = f"<b>{article['title']}</b>\n\n{summary}\n\n<i>{article['source']}</i>\n{hashtags}"

        try:
            if article["image"]:
                await bot.send_photo(chat_id=CHANNEL_ID, photo=article["image"], caption=caption)
            else:
                await bot.send_message(chat_id=CHANNEL_ID, text=caption)
            sent_titles.append(article["title"])
        except Exception as e:
            logging.error(f"Failed to send news: {e}")

    save_sent_titles(sent_titles)

async def main():
    while True:
        await send_news()
        await asyncio.sleep(60)  # Check every 60 seconds

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
