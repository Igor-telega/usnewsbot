import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
import openai
import requests
from aiogram import Bot, Dispatcher
from aiogram.types import InputMediaPhoto, InputFile
from aiogram.enums import ParseMode
from dotenv import load_dotenv
from feedparser import parse
from embeddings import get_embedding, is_duplicate, save_embedding
from image_gen import generate_image

load_dotenv()

# Настройки
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
MAX_PER_SOURCE = 2

openai.api_key = OPENAI_API_KEY
logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN, default=ParseMode.HTML)
dp = Dispatcher()

# RSS-источники
rss_feeds = {
    "NY Times": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "Reuters": "http://feeds.reuters.com/reuters/topNews",
    "CNN": "http://rss.cnn.com/rss/cnn_topstories.rss"
}

def load_sent_titles():
    try:
        with open("sent_titles.json", "r") as f:
            return json.load(f)["titles"]
    except FileNotFoundError:
        return []

def save_sent_titles(titles):
    with open("sent_titles.json", "w") as f:
        json.dump({"titles": titles}, f)

async def summarize_article(title, content, source):
    try:
        messages = [
            {"role": "system", "content": "Ты профессиональный новостной редактор."},
            {"role": "user", "content": f"Сделай краткое, нейтральное, журналистское описание новости под названием '{title}' из источника {source}. Основывайся на этом содержании:\n\n{content}"}
        ]

        response = await openai.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"Error with summary/image: {e}")
        return None

async def post_to_channel(article):
    title = article["title"]
    link = article["link"]
    summary = await summarize_article(title, article.get("summary", ""), article["source"])
    if not summary:
        return

    embedding = get_embedding(summary)
    if is_duplicate(embedding, "embeddings_storage.py"):
        return

    save_embedding(title, embedding)

    try:
        image_prompt = f"Generate a realistic news photo based on: {title}"
        image_url = generate_image(image_prompt)
    except Exception as e:
        logging.error(f"Error generating image: {e}")
        image_url = None

    content = f"<b>{title}</b>\n\n{summary}\n\nRead more: {link}"

    try:
        if image_url:
            await bot.send_photo(chat_id=CHANNEL_ID, photo=image_url, caption=content)
        else:
            await bot.send_message(chat_id=CHANNEL_ID, text=content)
    except Exception as e:
        logging.error(f"Error posting to Telegram: {e}")

async def main():
    sent_titles = load_sent_titles()
    articles_by_source = {source: [] for source in rss_feeds}

    now = datetime.utcnow()
    yesterday = now - timedelta(days=1)

    for source, url in rss_feeds.items():
        feed = parse(url)
        for entry in feed.entries:
            published = entry.get("published_parsed")
            if not published:
                continue
            published_dt = datetime(*published[:6])
            if published_dt < yesterday:
                continue
            article = {
                "title": entry.title,
                "link": entry.link,
                "summary": entry.get("summary", ""),
                "source": source
            }
            articles_by_source[source].append(article)

    for source, articles in articles_by_source.items():
        count = 0
        for article in articles:
            if article["title"] not in sent_titles:
                await post_to_channel(article)
                sent_titles.append(article["title"])
                await asyncio.sleep(5)
                count += 1
                if count >= MAX_PER_SOURCE:
                    break

    save_sent_titles(sent_titles)

if __name__ == "__main__":
    asyncio.run(main())
