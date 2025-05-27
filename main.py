import os
import asyncio
import logging
import json
from datetime import datetime, timedelta
import feedparser
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from openai import OpenAI
from embeddings import get_embedding, is_duplicate, save_embedding
from image_gen import generate_image

# Настройка логов
logging.basicConfig(level=logging.INFO)

# Переменные окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Telegram bot
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# RSS-источники
RSS_FEEDS = {
    "NYT": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "BBC": "http://feeds.bbci.co.uk/news/rss.xml",
    "CNN": "http://rss.cnn.com/rss/edition.rss"
}

# Загрузка уже отправленных заголовков
if os.path.exists("sent_titles.json"):
    with open("sent_titles.json", "r") as f:
        sent_titles = json.load(f)
else:
    sent_titles = []

# Получение свежих статей (за последние сутки)
def fetch_articles():
    all_articles = {source: [] for source in RSS_FEEDS}
    yesterday = datetime.utcnow() - timedelta(days=1)
    for source, url in RSS_FEEDS.items():
        feed = feedparser.parse(url)
        for entry in feed.entries:
            published = entry.get("published_parsed")
            if not published:
                continue
            pub_date = datetime(*published[:6])
            if pub_date > yesterday:
                all_articles[source].append({
                    "title": entry.title,
                    "link": entry.link,
                    "published": pub_date,
                    "source": source
                })
    return all_articles

# Получение краткого описания через OpenAI
async def summarize_article(title, source):
    try:
        prompt = f"Summarize the news article from {source} with the title: {title}. Keep it neutral and journalistic."
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"Error summarizing: {e}")
        return None

# Отправка новости в канал
async def post_to_channel(article):
    title = article["title"]
    if title in sent_titles:
        return

    embedding = get_embedding(title)
    if is_duplicate(embedding, "embeddings_storage.py"):
        return

    summary = await summarize_article(title, article["source"])
    if not summary:
        return

    try:
        image_url = generate_image(title)
        content = f"<b>{title}</b>\n\n{summary}\n\nSource: {article['source']}"
        await bot.send_photo(chat_id=CHANNEL_ID, photo=image_url, caption=content)
    except Exception as e:
        logging.error(f"Error posting to Telegram: {e}")

    sent_titles.append(title)
    save_embedding(title, embedding)

    with open("sent_titles.json", "w") as f:
        json.dump(sent_titles, f)

# Основной запуск
async def main():
    articles_by_source = fetch_articles()
    sources = list(articles_by_source.keys())
    max_articles = max(len(arts) for arts in articles_by_source.values())

    for i in range(max_articles):
        for source in sources:
            if i < len(articles_by_source[source]):
                await post_to_channel(articles_by_source[source][i])
                await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(main())

