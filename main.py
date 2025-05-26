import os
import time
import requests
import json
import feedparser
from datetime import datetime, timedelta
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from embeddings_storage import is_duplicate, save_embedding
from openai import OpenAI

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=TELEGRAM_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

client = OpenAI(api_key=OPENAI_API_KEY)

SOURCES = [
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "https://www.theguardian.com/world/rss",
    "http://rss.cnn.com/rss/edition_world.rss"
]

def get_article_date(entry):
    try:
        published = entry.get("published_parsed")
        if published:
            return datetime(*published[:6])
    except Exception:
        pass
    return None

def is_recent(entry, hours=24):
    article_date = get_article_date(entry)
    if article_date:
        return datetime.utcnow() - article_date <= timedelta(hours=hours)
    return False

def extract_image(entry):
    media_content = entry.get("media_content")
    if media_content and isinstance(media_content, list):
        return media_content[0].get("url")
    if "image" in entry:
        return entry["image"]
    return None

def extract_tags(text, max_tags=3):
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Generate 3 concise, relevant hashtags based on the topic of the article. Respond only with hashtags, space-separated."},
                {"role": "user", "content": text}
            ],
            temperature=0.7
        )
        tags_line = response.choices[0].message.content.strip()
        tags = tags_line.replace("#", "").split()
        return ["#" + tag for tag in tags[:max_tags]]
    except Exception as e:
        print(f"Ошибка при генерации хэштегов: {e}")
        return []

def embed_title(title):
    response = client.embeddings.create(
        input=title,
        model="text-embedding-ada-002"
    )
    return response.data[0].embedding

def create_caption(entry, source_name, tags, published_date):
    caption = f"<b>{entry.get('title')}</b>\n\n"
    caption += f"{entry.get('summary')}\n\n"
    caption += f"<b>Source:</b> <a href='{entry.get('link')}'>Link</a>\n"
    caption += f"🕒 <i>Published: {published_date.strftime('%B %d, %Y')}</i>\n"
    caption += f"<i>{source_name}</i>\n"
    caption += " ".join(tags)
    return caption

def extract_source_name(feed_url):
    if "nytimes" in feed_url:
        return "NYT"
    elif "guardian" in feed_url:
        return "The Guardian"
    elif "cnn" in feed_url:
        return "CNN"
    return "Unknown"

def fetch_and_post():
    for url in SOURCES:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            if not is_recent(entry):
                continue

            title = entry.get("title", "")
            embedding = embed_title(title)

            if is_duplicate(embedding):
                print(f"Пропущено как дубликат: {title}")
                continue

            save_embedding(title, embedding)

            summary = entry.get("summary", "")
            text_for_tags = f"{title}\n{summary}"
            tags = extract_tags(text_for_tags)

            image_url = extract_image(entry)
            source_name = extract_source_name(url)
            published_date = get_article_date(entry) or datetime.utcnow()
            caption = create_caption(entry, source_name, tags, published_date)

            try:
                if image_url:
                    bot.send_photo(chat_id=CHANNEL_ID, photo=image_url, caption=caption)
                else:
                    bot.send_message(chat_id=CHANNEL_ID, text=caption)
                time.sleep(2)
            except Exception as e:
                print(f"Ошибка при отправке: {e}")

if __name__ == "__main__":
    fetch_and_post()
