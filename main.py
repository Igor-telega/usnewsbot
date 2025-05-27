import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
import requests
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.types import InputFile
from feedparser import parse
from embeddings import get_embedding, is_duplicate, save_embedding
from image_gen import generate_image
from openai import OpenAI

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

openai_client = OpenAI(api_key=OPENAI_API_KEY)
logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN, default=ParseMode.HTML)
dp = Dispatcher()

rss_feeds = {
    "NY Times": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "Reuters": "http://feeds.reuters.com/reuters/topNews",
    "CNN": "http://rss.cnn.com/rss/cnn_topstories.rss",
    "AP News": "https://apnews.com/rss",
    "The Guardian": "https://www.theguardian.com/world/rss",
    "NPR": "https://feeds.npr.org/1001/rss.xml"
}

MAX_PER_SOURCE = 1
TIME_LIMIT_HOURS = 1
SENT_TITLES_FILE = "sent_titles.json"

def load_sent_titles():
    try:
        with open(SENT_TITLES_FILE, "r") as f:
            return json.load(f)["titles"]
    except FileNotFoundError:
        return []

def save_sent_titles(titles):
    with open(SENT_TITLES_FILE, "w") as f:
        json.dump({"titles": titles}, f)

async def summarize_article(title, content, source):
    try:
        messages = [
            {"role": "system", "content": "You are a professional news editor writing for an American audience. Write a concise, neutral, journalistic summary of the article in 6-10 sentences."},
            {"role": "user", "content": f"Title: {title}\nSource: {source}\nContent:\n{content}"}
        ]
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"Error with summary: {e}")
        return None

async def post_to_channel(article):
    title = article.get("title", "Untitled")
    summary = await summarize_article(title, article.get("summary", ""), article.get("source", "Unknown Source"))
    if not summary:
        return

    embedding = get_embedding(summary)
    if is_duplicate(embedding, "embeddings_storage.py"):
        return
    save_embedding(title, embedding)

    # Генерация изображения
    image_url = None
    try:
        image_prompt = f"Photorealistic image for a news headline: {title}. Context: {summary[:150]}"
        image_data = generate_image(image_prompt)
        if isinstance(image_data, dict):
            data_list = image_data.get("data")
            if isinstance(data_list, list) and len(data_list) > 0:
                image_url = data_list[0].get("url")
    except Exception as e:
        logging.error(f"Error generating image: {e}")
        image_url = None

    # Формат поста
    try:
        date_str = article.get("published", datetime.utcnow()).strftime('%Y-%m-%d %H:%M UTC')
    except Exception as e:
        logging.warning(f"Error formatting date: {e}")
        date_str = "Unknown time"

    try:
        message = (
            f"<b>{str(title)}</b>\n\n"
            f"{str(summary)}\n\n"
            f"<i>{str(article.get('source', ''))} | {str(date_str)}</i>\n#News #AI"
        )
    except Exception as e:
        logging.error(f"Error building message: {e}")
        return

    # Финальная защита от ошибок Telegram
    try:
        if isinstance(image_url, str) and image_url.startswith("http"):
            await bot.send_photo(chat_id=CHANNEL_ID, photo=image_url, caption=message[:1024])
        else:
            await bot.send_message(chat_id=CHANNEL_ID, text=message[:4096])
    except Exception as e:
        logging.error(f"Final posting error: {str(e)}")

async def main():
    sent_titles = load_sent_titles()
    articles_by_source = {source: [] for source in rss_feeds}

    now = datetime.utcnow()
    limit_time = now - timedelta(hours=TIME_LIMIT_HOURS)

    for source, url in rss_feeds.items():
        feed = parse(url)
        for entry in feed.entries:
            published_parsed = entry.get("published_parsed")
            if not published_parsed:
                continue
            published_dt = datetime(*published_parsed[:6])
            if published_dt < limit_time:
                continue
            article = {
                "title": entry.title,
                "link": entry.link,
                "summary": entry.get("summary", ""),
                "published": published_dt,
                "source": source
            }
            articles_by_source[source].append(article)

    # Чередуем источники
    all_articles = []
    max_len = max(len(arts) for arts in articles_by_source.values())
    for i in range(max_len):
        for source, articles in articles_by_source.items():
            if i < len(articles):
                all_articles.append(articles[i])

    # Публикация
    count_by_source = {s: 0 for s in rss_feeds}
    for article in all_articles:
        source = article["source"]
        if article["title"] not in sent_titles and count_by_source[source] < MAX_PER_SOURCE:
            await post_to_channel(article)
            sent_titles.append(article["title"])
            count_by_source[source] += 1
            await asyncio.sleep(5)

    save_sent_titles(sent_titles)
    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
