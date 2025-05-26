import os
import json
import asyncio
import feedparser
import requests
from aiogram import Bot, Dispatcher
from aiogram.types import InputFile
from aiogram.enums import ParseMode
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

client = OpenAI(api_key=OPENAI_API_KEY)

RSS_FEED_URL = f"https://newsapi.org/v2/top-headlines?country=us&apiKey={NEWS_API_KEY}"

SENT_TITLES_FILE = "/data/sent_titles.json"


def load_sent_titles():
    if not os.path.exists(SENT_TITLES_FILE):
        return []
    with open(SENT_TITLES_FILE, "r") as file:
        try:
            data = json.load(file)
            return data.get("titles", [])
        except json.JSONDecodeError:
            return []


def save_sent_titles(titles):
    with open(SENT_TITLES_FILE, "w") as file:
        json.dump({"titles": titles}, file)


def fetch_news():
    response = requests.get(RSS_FEED_URL)
    data = response.json()
    articles = data.get("articles", [])
    return articles


def summarize_text(text):
    prompt = f"Summarize the following news in one short sentence:\n\n{text}"
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()


async def send_news():
    sent_titles = load_sent_titles()
    news = fetch_news()

    for article in news:
        title = article.get("title")
        description = article.get("description", "")
        url = article.get("url", "")
        image_url = article.get("urlToImage", "")

        if title in sent_titles:
            continue

        summary = summarize_text(f"{title}\n\n{description}")
        caption = f"<b>{title}</b>\n\n{summary}\n\n<a href=\"{url}\">Read more</a>"

        try:
            if image_url:
                image_data = requests.get(image_url)
                with open("temp.jpg", "wb") as f:
                    f.write(image_data.content)
                await bot.send_photo(chat_id=CHANNEL_ID, photo=InputFile("temp.jpg"), caption=caption, parse_mode=ParseMode.HTML)
                os.remove("temp.jpg")
            else:
                await bot.send_message(chat_id=CHANNEL_ID, text=caption, parse_mode=ParseMode.HTML)
        except Exception as e:
            print("Error sending news:", e)

        sent_titles.append(title)
        save_sent_titles(sent_titles)
        await asyncio.sleep(2)


async def main():
    while True:
        await send_news()
        await asyncio.sleep(600)  # проверка каждые 10 минут


if __name__ == "__main__":
    asyncio.run(main())
