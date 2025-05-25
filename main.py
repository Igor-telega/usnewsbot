import os
import json
import requests
import asyncio
import logging
from PIL import Image
from io import BytesIO
import feedparser
import openai
from telegram import Bot

# Настройки
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=BOT_TOKEN)
openai.api_key = OPENAI_API_KEY

# Загружаем отправленные заголовки
SENT_TITLES_FILE = "sent_titles.json"
if os.path.exists(SENT_TITLES_FILE):
    with open(SENT_TITLES_FILE, "r") as f:
        sent_titles = json.load(f).get("titles", [])
else:
    sent_titles = []

def save_sent_title(title):
    sent_titles.append(title)
    with open(SENT_TITLES_FILE, "w") as f:
        json.dump({"titles": sent_titles}, f)

async def fetch_news():
    url = f"https://newsapi.org/v2/top-headlines?country=us&apiKey={NEWS_API_KEY}"
    response = requests.get(url)
    data = response.json()
    return data["articles"]

async def generate_summary(title, description):
    prompt = f"Summarize the following news in one short sentence:

Title: {title}
Description: {description}"
    try:
        chat_response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=60,
            temperature=0.7,
        )
        return chat_response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"OpenAI Error: {e}")
        return "Short summary unavailable."

async def send_news():
    articles = await fetch_news()
    for article in articles:
        title = article["title"]
        if title in sent_titles:
            continue

        summary = await generate_summary(title, article.get("description", ""))
        image_url = article.get("urlToImage")
        text = f"<b>{title}</b>

{summary}"

        try:
            if image_url:
                response = requests.get(image_url)
                image = BytesIO(response.content)
                await bot.send_photo(chat_id=CHANNEL_ID, photo=image, caption=text, parse_mode="HTML")
            else:
                await bot.send_message(chat_id=CHANNEL_ID, text=text, parse_mode="HTML")

            save_sent_title(title)
            await asyncio.sleep(2)
        except Exception as e:
            logging.error(f"Telegram Error: {e}")

if __name__ == "__main__":
    asyncio.run(send_news())
