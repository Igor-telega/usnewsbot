import os
import json
import time
import feedparser
import openai
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import InputFile
from datetime import datetime
import requests
from io import BytesIO

# Получение переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

NEWS_URL = f"https://newsapi.org/v2/top-headlines?country=us&apiKey={NEWS_API_KEY}"

# Локальный файл
SENT_TITLES_FILE = "sent_titles.json"

# Загрузка отправленных заголовков
def load_sent_titles():
    if not os.path.exists(SENT_TITLES_FILE):
        return []
    with open(SENT_TITLES_FILE, "r") as f:
        try:
            data = json.load(f)
            return data.get("titles", [])
        except json.JSONDecodeError:
            return []

# Сохранение отправленных заголовков
def save_sent_titles(titles):
    with open(SENT_TITLES_FILE, "w") as f:
        json.dump({"titles": titles}, f)

# Генерация краткой сводки
def generate_summary(title, description):
    prompt = f"Summarize the following news in one short sentence:\nTitle: {title}\nDescription: {description}"
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=50
    )
    return response.choices[0].message["content"].strip()

# Отправка новостей в Telegram
async def send_news():
    sent_titles = load_sent_titles()

    response = requests.get(NEWS_URL)
    news_data = response.json()
    articles = news_data.get("articles", [])

    for article in articles:
        title = article["title"]
        description = article.get("description", "")
        image_url = article.get("urlToImage")

        if title in sent_titles:
            continue

        summary = generate_summary(title, description)

        caption = f"<b>{title}</b>\n\n{summary}"
        try:
            if image_url:
                img_data = requests.get(image_url).content
                image = InputFile(BytesIO(img_data), filename="image.jpg")
                await bot.send_photo(chat_id=CHANNEL_ID, photo=image, caption=caption, parse_mode="HTML")
            else:
                await bot.send_message(chat_id=CHANNEL_ID, text=caption, parse_mode="HTML")
        except Exception as e:
            print("Error sending news:", e)

        sent_titles.append(title)
        save_sent_titles(sent_titles)
        time.sleep(3)

if __name__ == "__main__":
    asyncio.run(send_news())
