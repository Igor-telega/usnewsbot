import os
import json
import asyncio
import feedparser
from aiogram import Bot, Dispatcher
from aiogram.types import InputFile
from openai import OpenAI
from dotenv import load_dotenv
import requests

load_dotenv()

# Загружаем ключи из переменных среды
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
client = OpenAI(api_key=OPENAI_API_KEY)

# Загружаем уже опубликованные заголовки
def load_sent_titles():
    try:
        with open("sent_titles.json", "r") as f:
            return json.load(f)["titles"]
    except (FileNotFoundError, json.JSONDecodeError):
        return []

# Сохраняем новые заголовки
def save_sent_titles(titles):
    with open("sent_titles.json", "w") as f:
        json.dump({"titles": titles}, f)

# Генерация краткой сводки
def generate_summary(title, description):
    prompt = f"Summarize the following news in one short sentence:\n\nTitle: {title}\n\nDescription: {description}"
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

# Получение изображения
def get_image_url(article):
    return article.get("urlToImage")

# Отправка новости
async def send_news():
    sent_titles = load_sent_titles()

    url = f"https://newsapi.org/v2/top-headlines?country=us&apiKey={NEWS_API_KEY}"
    response = requests.get(url)
    articles = response.json().get("articles", [])

    for article in articles:
        title = article["title"]
        description = article.get("description", "")
        image_url = get_image_url(article)

        if title in sent_titles:
            continue

        summary = generate_summary(title, description)

        try:
            if image_url:
                image_data = requests.get(image_url).content
                with open("temp.jpg", "wb") as f:
                    f.write(image_data)
                photo = InputFile("temp.jpg")
                await bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=f"{title}\n\n{summary}")
            else:
                await bot.send_message(chat_id=CHANNEL_ID, text=f"{title}\n\n{summary}")
        except Exception as e:
            print("Error sending news:", e)
            continue

        sent_titles.append(title)
        save_sent_titles(sent_titles)

        await asyncio.sleep(3)  # Пауза между публикациями

if __name__ == "__main__":
    asyncio.run(send_news())
