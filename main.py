import asyncio
import os
import feedparser
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.types import FSInputFile
from aiogram.enums import ParseMode
from dotenv import load_dotenv
from datetime import datetime
import json
import openai

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

RSS_FEEDS = {
    "NYT": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "CNN": "http://rss.cnn.com/rss/cnn_topstories.rss",
    "Reuters": "http://feeds.reuters.com/reuters/topNews",
    "AP": "https://apnews.com/rss",
    "The Guardian": "https://www.theguardian.com/world/rss"
}

MAX_POSTS_PER_RUN = 5
SENT_TITLES_FILE = "sent_titles.json"

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

def load_sent_titles():
    if not os.path.exists(SENT_TITLES_FILE):
        return []
    with open(SENT_TITLES_FILE, "r") as file:
        data = json.load(file)
        return data.get("titles", [])

def save_sent_titles(titles):
    with open(SENT_TITLES_FILE, "w") as file:
        json.dump({"titles": titles}, file)

async def summarize_text(text):
    response = openai.ChatCompletion.acreate(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Ты — новостной редактор. Преобразуй статью в сжатый, но полный пересказ от третьего лица. Не пиши: 'в статье рассказывается'. Просто изложи суть статьи своими словами в 4-6 предложениях, чтобы было понятно, в чём новость. Сохраняй нейтральный тон."},
            {"role": "user", "content": text}
        ]
    )
    return response.choices[0].message.content.strip()

async def generate_image(prompt):
    try:
        response = openai.Image.acreate(
            model="dall-e-3",
            prompt=prompt,
            n=1,
            size="1024x1024"
        )
        image_url = response.data[0].url
        image_data = requests.get(image_url).content
        with open("ai_image.jpg", "wb") as f:
            f.write(image_data)
        return "ai_image.jpg"
    except Exception as e:
        print(f"Image generation failed: {e}")
        return None

async def fetch_and_send_news():
    sent_titles = load_sent_titles()
    new_titles = []

    for source, url in RSS_FEEDS.items():
        feed = feedparser.parse(url)
        count = 0
        for entry in feed.entries:
            if entry.title in sent_titles:
                continue

            summary = getattr(entry, 'summary', '') or getattr(entry, 'description', '')
            full_text = f"{entry.title}\n\n{summary}"
            try:
                summarized = await summarize_text(full_text)
            except Exception as e:
                print(f"OpenAI summarization error: {e}")
                continue

            message = f"<b>{entry.title}</b>\n\n{summarized}\n\n<i>{source}</i>\n#AI #World"

            image_url = None
            if "media_content" in entry and entry.media_content:
                image_url = entry.media_content[0].get("url")
            elif "media_thumbnail" in entry and entry.media_thumbnail:
                image_url = entry.media_thumbnail[0].get("url")

            image_path = None
            if image_url:
                try:
                    image_data = requests.get(image_url, timeout=10).content
                    with open("temp.jpg", "wb") as f:
                        f.write(image_data)
                    image_path = "temp.jpg"
                except Exception as e:
                    print(f"Failed to fetch original image: {e}")
            else:
                # Генерируем картинку, если своей нет
                image_path = await generate_image(entry.title)

            try:
                if image_path:
                    photo = FSInputFile(image_path)
                    await bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=message, parse_mode=ParseMode.HTML)
                    os.remove(image_path)
                else:
                    await bot.send_message(chat_id=CHANNEL_ID, text=message, parse_mode=ParseMode.HTML)
            except Exception as e:
                print(f"Error sending message: {e}")

            new_titles.append(entry.title)
            count += 1
            if count >= MAX_POSTS_PER_RUN:
                break

    save_sent_titles(sent_titles + new_titles)

async def main():
    while True:
        try:
            await fetch_and_send_news()
        except Exception as e:
            print(f"Error during news fetch: {e}")
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
