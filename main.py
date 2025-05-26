import asyncio
import os
import feedparser
import requests
import openai
import json
from datetime import datetime
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.types import InputFile
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

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

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

def load_sent_titles():
    if not os.path.exists(SENT_TITLES_FILE):
        return []
    with open(SENT_TITLES_FILE, "r") as file:
        return json.load(file).get("titles", [])

def save_sent_titles(titles):
    with open(SENT_TITLES_FILE, "w") as file:
        json.dump({"titles": titles}, file)

async def summarize_text(text):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ты журналист. Напиши краткий пересказ этой статьи простыми словами. Это не аннотация, а пересказ сути. Не пиши, что это статья или она рассказывает о чем-то. Просто перескажи содержание своими словами в 3–5 предложениях для поста в Telegram."},
                {"role": "user", "content": text}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("OpenAI summarization error:", e)
        return None

async def generate_image(prompt):
    try:
        dalle = openai.Image.create(
            prompt=prompt,
            n=1,
            size="1024x1024"
        )
        return dalle["data"][0]["url"]
    except Exception as e:
        print("DALL·E image generation error:", e)
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
            text = f"{entry.title}\n{summary}"
            summarized = await summarize_text(text)

            if not summarized:
                print("Skipping:", entry.title)
                continue

            hashtags = "#AI #World"
            message = f"<b>{entry.title}</b>\n\n{summarized}\n\n<i>{source}</i>\n{hashtags}"

            image_url = None
            if "media_content" in entry and entry.media_content:
                image_url = entry.media_content[0].get("url")
            elif "image" in entry:
                image_url = entry.image.get("href")

            try:
                if image_url:
                    image_data = requests.get(image_url).content
                    with open("temp.jpg", "wb") as f:
                        f.write(image_data)
                    photo = InputFile("temp.jpg")
                    await bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=message)
                    os.remove("temp.jpg")
                else:
                    # generate DALL·E image
                    prompt = entry.title
                    img_link = await generate_image(prompt)
                    if img_link:
                        await bot.send_photo(chat_id=CHANNEL_ID, photo=img_link, caption=message)
                    else:
                        await bot.send_message(chat_id=CHANNEL_ID, text=message)

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
            print("Error in fetch loop:", e)
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
