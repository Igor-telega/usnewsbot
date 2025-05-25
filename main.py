import os
import json
import asyncio
import feedparser
import requests
from aiogram import Bot, Dispatcher
from aiogram.types import InputFile
from openai import OpenAI

# Загружаем переменные окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Инициализация бота и OpenAI
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
client = OpenAI(api_key=OPENAI_API_KEY)

SENT_TITLES_FILE = "sent_titles.json"

# Загружаем уже отправленные заголовки
if os.path.exists(SENT_TITLES_FILE):
    with open(SENT_TITLES_FILE, "r") as f:
        sent_titles = json.load(f)["titles"]
else:
    sent_titles = []

# Получаем новости с NewsAPI
def get_news():
    url = (
        f"https://newsapi.org/v2/top-headlines?country=us&pageSize=5&apiKey={NEWS_API_KEY}"
    )
    response = requests.get(url)
    articles = response.json().get("articles", [])
    return articles

# Генерируем краткое описание через OpenAI
def generate_summary(title, content):
    prompt = f"Summarize the following news story in one short sentence:\n\nTitle: {title}\n\nContent: {content}"
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )
    return response.choices[0].message.content.strip()

# Отправка новостей в Telegram
async def send_news():
    articles = get_news()
    for article in articles:
        title = article.get("title")
        content = article.get("description", "")
        url = article.get("url")
        image_url = article.get("urlToImage")

        if title in sent_titles:
            continue

        try:
            summary = generate_summary(title, content)

            caption = f"<b>{title}</b>\n\n{summary}"
            if url:
                caption += f"\n\n<a href='{url}'>Read more</a>"

            if image_url:
                image_data = requests.get(image_url).content
                with open("temp.jpg", "wb") as f:
                    f.write(image_data)
                photo = InputFile("temp.jpg")
                await bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=caption, parse_mode="HTML")
                os.remove("temp.jpg")
            else:
                await bot.send_message(chat_id=CHANNEL_ID, text=caption, parse_mode="HTML")

            sent_titles.append(title)
            with open(SENT_TITLES_FILE, "w") as f:
                json.dump({"titles": sent_titles}, f)

            await asyncio.sleep(5)

        except Exception as e:
            print("Error sending news:", e)

# Запуск
async def main():
    await send_news()
    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
