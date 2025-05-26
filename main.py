import asyncio
import os
import feedparser
import requests
import hashlib
from openai import AsyncOpenAI
from aiogram import Bot, Dispatcher
from aiogram.types import FSInputFile
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv
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
SENT_HASHES_FILE = "sent_titles.json"

def load_sent_hashes():
    if not os.path.exists(SENT_HASHES_FILE):
        return []
    with open(SENT_HASHES_FILE, "r") as file:
        data = json.load(file)
        return data.get("hashes", [])

def save_sent_hashes(hashes):
    with open(SENT_HASHES_FILE, "w") as file:
        json.dump({"hashes": hashes}, file)

def generate_hash(title, summary):
    combined = (title + summary).strip().lower()
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()

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
    sent_hashes = load_sent_hashes()
    new_hashes = []

    for source, url in RSS_FEEDS.items():
        feed = feedparser.parse(url)
        count = 0
        for entry in feed.entries:
            summary = getattr(entry, 'summary', '') or getattr(entry, 'description', '')
            news_hash = generate_hash(entry.title, summary)

            if news_hash in sent_hashes or news_hash in new_hashes:
                continue

            try:
                summarized = await summarize_article(entry.title, summary)
                hashtags = await generate_hashtags(summarized)
            except Exception as e:
                print("OpenAI summarization error:", e)
                continue

            message = f"<b>{entry.title}</b>\n\n{summarized}\n\n<i>{source}</i>\n{hashtags}"
            image_url = None
            if "media_content" in entry and entry.media_content:
                image_url = entry.media_content[0].get("url")

            try:
                if image_url:
                    image_data = requests.get(image_url).content
                    with open("temp.jpg", "wb") as f:
                        f.write(image_data)
                    await bot.send_photo(chat_id=CHANNEL_ID, photo=FSInputFile("temp.jpg"), caption=message)
                    os.remove("temp.jpg")
                else:
                    img_prompt = f"Realistic illustration related to: {entry.title}"
                    img_link = await generate_image(img_prompt)
                    if img_link:
                        img_data = requests.get(img_link).content
                        with open("temp.jpg", "wb") as f:
                            f.write(img_data)
                        await bot.send_photo(chat_id=CHANNEL_ID, photo=FSInputFile("temp.jpg"), caption=message)
                        os.remove("temp.jpg")
                    else:
                        await bot.send_message(chat_id=CHANNEL_ID, text=message)
            except Exception as e:
                print("Sending error:", e)

            new_hashes.append(news_hash)
            count += 1
            if count >= MAX_POSTS_PER_RUN:
                break

    save_sent_hashes(sent_hashes + new_hashes)

async def main():
    while True:
        try:
            await fetch_and_send_news()
        except Exception as e:
            print("Main loop error:", e)
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
