import feedparser
import asyncio
import json
import os
import logging
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.types import Message
import httpx

# Загрузка переменных окружения
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Настройка логгирования
logging.basicConfig(level=logging.INFO)

# RSS-источники
RSS_FEEDS = {
    "NYTimes": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "Reuters": "http://feeds.reuters.com/reuters/topNews",
    "CNN": "http://rss.cnn.com/rss/edition.rss",
    "APNews": "https://www.apnews.com/rss",
    "The Guardian": "https://www.theguardian.com/world/rss",
    "NPR": "https://www.npr.org/rss/rss.php?id=1001",
}

# Параметры публикации
MAX_ARTICLES = 1
POST_DELAY = 8  # секунд
HOURS_LIMIT = 2

# Telegram bot
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# Загрузка опубликованных заголовков
if os.path.exists("sent_titles.json"):
    with open("sent_titles.json", "r") as f:
        sent_titles = set(json.load(f))
else:
    sent_titles = set()

# Сохранение заголовков
def save_sent_titles():
    with open("sent_titles.json", "w") as f:
        json.dump(list(sent_titles), f)

# Проверка, свежая ли новость
def is_recent(entry):
    published = entry.get("published_parsed")
    if not published:
        return False
    pub_time = datetime(*published[:6], tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - pub_time < timedelta(hours=HOURS_LIMIT)

# Генерация summary через OpenAI
async def generate_summary(title, content):
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    prompt = (
        f"Ты — нейтральный новостной редактор. Составь краткую новостную сводку по следующей информации.\n\n"
        f"Заголовок: {title}\n\n"
        f"Содержание: {content}\n\n"
        f"Сводка:"
    )
    data = {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 350,
        "temperature": 0.7,
    }

    async with httpx.AsyncClient() as client:
        response = await client.post("https://api.openai.com/v1/chat/completions", json=data, headers=headers, timeout=30)
        result = response.json()
        return result["choices"][0]["message"]["content"].strip()

# Публикация в Telegram
async def post_to_telegram(title, summary, source, link):
    hashtags = "#News #AI"
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    message = (
        f"<b>{title}</b>\n\n"
        f"{summary}\n\n"
        f"<i>{source} — {now}</i>\n"
        f"{hashtags}"
    )
    await bot.send_message(chat_id=CHANNEL_ID, text=message, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

# Основной цикл
async def fetch_and_post():
    for source, url in RSS_FEEDS.items():
        feed = feedparser.parse(url)
        count = 0

        for entry in feed.entries:
            if count >= MAX_ARTICLES:
                break

            title = entry.title.strip()
            link = entry.link
            summary_text = entry.get("summary", "")[:1000]

            if title in sent_titles or not is_recent(entry):
                continue

            try:
                summary = await generate_summary(title, summary_text)
                await post_to_telegram(title, summary, source, link)
                sent_titles.add(title)
                count += 1
                save_sent_titles()
                await asyncio.sleep(POST_DELAY)
            except Exception as e:
                logging.error(f"Error processing article '{title}': {e}")

# Запуск
if __name__ == "__main__":
    asyncio.run(fetch_and_post())
