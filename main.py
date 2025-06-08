import feedparser
import asyncio
import os
import json
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from aiogram import Bot
from aiogram.enums import ParseMode
import httpx
import logging

# === Настройки ===

# Загрузка переменных окружения
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

SOURCE_NAME = os.getenv("SOURCE_NAME", "CNN")
RSS_URL = os.getenv("RSS_URL", "http://rss.cnn.com/rss/edition.rss")
HOURS_LIMIT = 2
POST_DELAY = 8

# Настройка логов
logging.basicConfig(level=logging.INFO)

# Telegram bot
bot = Bot(token=TELEGRAM_TOKEN)

# Загруженные заголовки
DATA_FILE = f"sent_{SOURCE_NAME.lower()}.json"
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        sent_titles = set(json.load(f))
else:
    sent_titles = set()

def save_titles():
    with open(DATA_FILE, "w") as f:
        json.dump(list(sent_titles), f)

# Проверка свежести
def is_recent(entry):
    pub = entry.get("published_parsed")
    if not pub:
        return False
    pub_time = datetime(*pub[:6], tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - pub_time < timedelta(hours=HOURS_LIMIT)

# Генерация краткой сводки
async def generate_summary(title, content):
    prompt = (
        f"You are a neutral news editor. Based on the following headline and content, "
        f"write a short news summary in English, 6–10 sentences, neutral journalistic style.\n\n"
        f"Headline: {title}\n\nContent: {content}\n\nSummary:"
    )
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 350,
        "temperature": 0.7
    }

    async with httpx.AsyncClient() as client:
        response = await client.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers)
        return response.json()["choices"][0]["message"]["content"].strip()

# Публикация
async def post_to_channel(title, summary):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    hashtags = "#News #AI"
    text = (
        f"<b>{title}</b>\n\n"
        f"{summary}\n\n"
        f"<i>{SOURCE_NAME} — {now}</i>\n"
        f"{hashtags}"
    )
    await bot.send_message(chat_id=CHANNEL_ID, text=text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

# Основная логика
async def run_bot():
    feed = feedparser.parse(RSS_URL)

    for entry in feed.entries[:3]:  # максимум 3 новости за запуск
        title = entry.title.strip()
        if title in sent_titles or not is_recent(entry):
            continue

        content = entry.get("summary", "")[:1000]

        try:
            summary = await generate_summary(title, content)
            await post_to_channel(title, summary)
            sent_titles.add(title)
            save_titles()
            await asyncio.sleep(POST_DELAY)
        except Exception as e:
            logging.error(f"Error while processing {title}: {e}")

# Старт
if __name__ == "__main__":
    asyncio.run(run_bot())
