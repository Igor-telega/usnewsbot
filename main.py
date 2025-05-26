import asyncio
import os
import feedparser
import requests
import openai
from openai import AsyncOpenAI
from aiogram import Bot, Dispatcher
from aiogram.types import FSInputFile
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv
from datetime import datetime
import json

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = AsyncOpenAI(api_key=OPENAI_API_KEY)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

RSS_FEEDS = {
    "NYT": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "CNN": "http://rss.cnn.com/rss/cnn_topstories.rss",
    "Reuters": "http://feeds.reuters.com/reuters/topNews",
    "AP": "https://apnews.com/rss",
    "The Guardian": "https://www.theguardian.com/world/rss"
}

MAX_POSTS_PER_RUN = 5
SENT_TITLES_FILE = "sent_titles.json"

def load_sent_titles():
    if not os.path.exists(SENT_TITLES_FILE):
        return []
    with open(SENT_TITLES_FILE, "r") as file:
        data = json.load(file)
        return data.get("titles", [])

def save_sent_titles(titles):
    with open(SENT_TITLES_FILE, "w") as file:
        json.dump({"titles": titles}, file)

async def summarize_article(title, summary):
    prompt = f"""Summarize the following news article in 3–5 concise sentences in fluent English. Don't write that it's a news article or summary — just explain it in simple terms as if writing a news brief:

Title: {title}
Text: {summary}"""
    response = await client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

async def generate_hashtags(text):
    prompt = f"""Suggest 2–3 relevant English hashtags for the following news summary. Only return hashtags separated by spaces. No hashtags like #news or #breaking — be more specific.

Text: {text}"""
    response = await client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

async def generate_image(prompt):
    try:
        image_resp = await client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            n=1,
            size="1024x1024"
        )
        return image_resp.data[0].url
    except Exception as e:
        print("Image generation error:", e)
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
            image_url = None
            if "media_content" in entry and entry.media_content:
                image_url = entry.media_content[0].get("url")

            article_text = f"{entry.title}\n{summary}"
            try:
                summarized = await summarize_article(entry.title, summary)
                hashtags = await generate_hashtags(summarized)
            except Exception as e:
                print("OpenAI summarization error:", e)
                continue

            message = f"<b>{entry.title}</b>\n\n{summarized}\n\n<i>{source}</i>\n{hashtags}"

            try:
                if image_url:
                    image_data = requests.get(image_url).content
                    with open("temp.jpg", "wb") as f:
                        f.write(image_data)
                    photo = FSInputFile("temp.jpg")
                    await bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=message)
                    os.remove("temp.jpg")
                else:
                    image_prompt = f"Realistic illustration related to: {entry.title}"
                    img_link = await generate_image(image_prompt)
                    if img_link:
                        img_data = requests.get(img_link).content
                        with open("temp.jpg", "wb") as f:
                            f.write(img_data)
                        photo = FSInputFile("temp.jpg")
                        await bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=message)
                        os.remove("temp.jpg")
                    else:
                        await bot.send_message(chat_id=CHANNEL_ID, text=message)
            except Exception as e:
                print("Error sending message:", e)

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
            print("Error in main loop:", e)
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
