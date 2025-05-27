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

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, default=ParseMode.HTML)
dp = Dispatcher()

rss_feeds = {
    "NY Times": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "Reuters": "http://feeds.reuters.com/reuters/topNews",
    "CNN": "http://rss.cnn.com/rss/cnn_topstories.rss",
    "AP": "https://apnews.com/rss",
    "NPR": "https://feeds.npr.org/1001/rss.xml",
    "The Guardian": "https://www.theguardian.com/world/rss",
    "Bloomberg": "https://www.bloomberg.com/feed/podcast/etf-report.xml",
    "BBC": "http://feeds.bbci.co.uk/news/rss.xml",
    "Al Jazeera": "https://www.aljazeera.com/xml/rss/all.xml",
    "NBC News": "https://feeds.nbcnews.com/nbcnews/public/news"
}

MAX_PER_SOURCE = 1
TIME_WINDOW_HOURS = 10

def load_sent_titles():
    try:
        with open("sent_titles.json", "r") as f:
            return json.load(f)["titles"]
    except FileNotFoundError:
        return []

def save_sent_titles(titles):
    with open("sent_titles.json", "w") as f:
        json.dump({"titles": titles}, f)

def format_datetime(dt_obj):
    return dt_obj.strftime("%b %d, %Y %H:%M")

def summarize_article(title, content, source):
    try:
        messages = [
            {"role": "system", "content": "Ты профессиональный новостной редактор. Пиши в сжатом, информативном стиле для американской аудитории."},
            {"role": "user", "content": f"Сделай краткое, логичное и информативное изложение новости под названием '{title}' из источника {source}. Основывайся на этом содержании:\n\n{content}"}
        ]
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"Error with summary: {e}")
        return None

async def post_to_channel(article):
    title = article["title"]
    link = article["link"]
    pub_date = article["published"]
    source = article["source"]
    summary = summarize_article(title, article.get("summary", ""), source)
    if not summary:
        return

    embedding = get_embedding(summary)
    if is_duplicate(embedding, "embeddings_storage.py"):
        return
    save_embedding(title, embedding)

    try:
        image_prompt = f"Realistic photo for news about: {title}"
        image_url = generate_image(image_prompt)
    except Exception as e:
        logging.error(f"Error generating image: {e}")
        image_url = None

    content = f"<b>{title}</b>\n\n{summary}\n\n<i>{source}, {pub_date}</i>"

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
    time_limit = now - timedelta(hours=TIME_WINDOW_HOURS)

    for source, url in rss_feeds.items():
        feed = parse(url)
        for entry in feed.entries:
            pub = entry.get("published_parsed")
            if not pub:
                continue
            pub_dt = datetime(*pub[:6])
            if pub_dt < time_limit:
                continue
            article = {
                "title": entry.title,
                "link": entry.link,
                "summary": entry.get("summary", ""),
                "published": format_datetime(pub_dt),
                "source": source
            }
            articles_by_source[source].append(article)

    count = 0
    max_news = MAX_PER_SOURCE * len(rss_feeds)
    for i in range(MAX_PER_SOURCE):
        for source in rss_feeds:
            if i < len(articles_by_source[source]):
                article = articles_by_source[source][i]
                if article["title"] not in sent_titles:
                    await post_to_channel(article)
                    sent_titles.append(article["title"])
                    count += 1
                    await asyncio.sleep(5)
            if count >= max_news:
                break

    save_sent_titles(sent_titles)

if __name__ == "__main__":
    asyncio.run(main())
