import os
import json
import asyncio
import logging
from datetime import datetime, timedelta

import openai
import requests
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from dotenv import load_dotenv
from feedparser import parse as feedparser_parse
from image_gen import generate_image
from embeddings import get_embedding, is_duplicate, save_embedding

load_dotenv()

# Настройки
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

openai.api_key = OPENAI_API_KEY
logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

RSS_FEEDS = {
    "CNN": "http://rss.cnn.com/rss/edition.rss",
    "Reuters": "http://feeds.reuters.com/reuters/topNews",
    "NYT": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"
}

def fetch_articles(feed_url):
    feed = feedparser_parse(feed_url)
    one_day_ago = datetime.utcnow() - timedelta(days=1)
    return [
        {
            "title": entry.title,
            "link": entry.link,
            "published": entry.published if "published" in entry else "",
            "summary": entry.summary if "summary" in entry else ""
        }
        for entry in feed.entries
        if "published_parsed" in entry and datetime(*entry.published_parsed[:6]) > one_day_ago
    ]

def summarize_article(title, summary, source):
    try:
        prompt = (
            f"Summarize the news article from {source} with the title: '{title}'. "
            f"Here is the content: {summary}\n\n"
            "Make it clear and engaging, like a news brief for a general audience. "
            "Format it as a short paragraph (2-3 sentences) and keep it neutral and journalistic."
        )
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"Error summarizing article: {e}")
        return None

async def post_to_channel(article):
    title = article["title"]
    link = article["link"]
    summary = summarize_article(title, article["summary"], "news source")

    if not summary:
        logging.error("Error with summary/image:")
        return

    embedding = get_embedding(title)
    if is_duplicate(embedding, "embeddings_storage.py"):
        logging.info("Duplicate article. Skipping.")
        return

    try:
        image_url = generate_image(title)
    except Exception as e:
        logging.error(f"Error generating image: {e}")
        image_url = None

    content = f"<b>{title}</b>\n\n{summary}\n\n<a href=\"{link}\">Read more</a>"
    try:
        if image_url:
            await bot.send_photo(chat_id=CHANNEL_ID, photo=image_url, caption=content)
        else:
            await bot.send_message(chat_id=CHANNEL_ID, text=content)
    except Exception as e:
        logging.error(f"Error posting to Telegram: {e}")
        return

    # Save embedding
    save_embedding(title, embedding)

    # Update sent_titles.json
    try:
        with open("sent_titles.json", "r+", encoding="utf-8") as f:
            data = json.load(f)
            data["titles"].append(title)
            f.seek(0)
            json.dump(data, f, indent=2)
            f.truncate()
    except Exception as e:
        logging.error(f"Error updating sent_titles.json: {e}")

async def main():
    try:
        with open("sent_titles.json", "r") as f:
            sent_titles_data = json.load(f)
        sent_titles = sent_titles_data.get("titles", [])
    except (FileNotFoundError, json.JSONDecodeError):
        sent_titles = []

    articles_by_source = {name: fetch_articles(url) for name, url in RSS_FEEDS.items()}
    for source, articles in articles_by_source.items():
        for article in articles:
            if article["title"] not in sent_titles:
                await post_to_channel(article)
                await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
