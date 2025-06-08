import os
import asyncio
import feedparser
import requests
from newspaper import Article
from aiogram import Bot, Dispatcher, types
from openai import OpenAI
from datetime import datetime

# Загрузка переменных окружения
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
RSS_URL = os.getenv("RSS_URL")
SOURCE_NAME = os.getenv("SOURCE_NAME", "News")

# Файл для отслеживания опубликованных ссылок
POSTED_URLS_FILE = "posted_urls.txt"

# Проверка, публиковалась ли уже ссылка
def is_already_posted(url):
    if not os.path.exists(POSTED_URLS_FILE):
        return False
    with open(POSTED_URLS_FILE, 'r') as f:
        posted = f.read().splitlines()
    return url in posted

# Сохраняем новую ссылку
def mark_as_posted(url):
    with open(POSTED_URLS_FILE, 'a') as f:
        f.write(url + '\n')

# Запуск бота
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

async def fetch_and_post_news():
    feed = feedparser.parse(RSS_URL)
    for entry in feed.entries[:5]:
        url = entry.link
        if is_already_posted(url):
            continue

        try:
            article = Article(url)
            article.download()
            article.parse()
            content = article.text

            if not content.strip():
                continue

            # Генерация краткой версии новости с помощью OpenAI
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a professional journalist. Summarize the article into a short, engaging news post suitable for Telegram."},
                    {"role": "user", "content": content}
                ],
                temperature=0.7,
                max_tokens=500
            )

            summary = response.choices[0].message.content.strip()

            # Отправка в Telegram
            date = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
            caption = f"🗞 <b>{entry.title}</b>\n\n{summary}\n\nSource: {SOURCE_NAME}\n{date} #News #{SOURCE_NAME}"
            await bot.send_message(CHANNEL_ID, caption, parse_mode="HTML")

            mark_as_posted(url)

        except Exception as e:
            print(f"Error: {e}")
            continue

async def main():
    await fetch_and_post_news()

if __name__ == "__main__":
    asyncio.run(main())
