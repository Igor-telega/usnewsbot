import asyncio
import os
import feedparser
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.types import InputFile
from dotenv import load_dotenv
from datetime import datetime, timedelta
import json
import openai
from embeddings import is_duplicate, save_embedding

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

def is_recent(entry):
    if hasattr(entry, "published_parsed"):
        published = datetime(*entry.published_parsed[:6])
        return datetime.utcnow() - published <= timedelta(days=1)
    return True

async def summarize_text(text):
    response = await openai.ChatCompletion.acreate(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a professional journalist writing for an American audience. Write a clear, concise news summary of the article below in 6–10 sentences."},
            {"role": "user", "content": text}
        ]
    )
    return response.choices[0].message.content.strip()

async def generate_image(prompt):
    try:
        response = await openai.Image.acreate(
            prompt=prompt,
            n=1,
            size="1024x1024"
        )
        return response['data'][0]['url']
    except Exception as e:
        print("Image generation failed:", e)
        return None

async def fetch_and_send_news():
    sent_titles = load_sent_titles()
    new_titles = []
    feed_entries_by_source = {}

    # Сбор свежих новостей
    for source, url in RSS_FEEDS.items():
        feed = feedparser.parse(url)
        fresh_entries = [entry for entry in feed.entries if is_recent(entry)]
        feed_entries_by_source[source] = fresh_entries

    # Публикация новостей поочередно
    for i in range(MAX_POSTS_PER_RUN):
        for source in RSS_FEEDS:
            entries = feed_entries_by_source.get(source, [])
            if i >= len(entries):
                continue

            entry = entries[i]
            if entry.title in sent_titles:
                continue

            summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
            full_text = f"{entry.title}\n\n{summary}"

            try:
                embedding_response = await openai.Embedding.acreate(
                    model="text-embedding-ada-002",
                    input=entry.title
                )
                new_embedding = embedding_response['data'][0]['embedding']
            except Exception as e:
                print("Embedding error:", e)
                continue

            if is_duplicate(new_embedding):
                continue

            summarized = await summarize_text(full_text)
            image_url = await generate_image(entry.title)

            message = f"<b>{entry.title}</b>\n\n{summarized}\n\n<i>{source}</i>\n#News #AI"

            try:
                if image_url:
                    photo = types.FSInputFile.from_url(image_url)
                    await bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=message)
                else:
                    await bot.send_message(chat_id=CHANNEL_ID, text=message)
            except Exception as e:
                print("Sending error:", e)

            new_titles.append(entry.title)
            save_embedding(entry.title, new_embedding)

    save_sent_titles(sent_titles + new_titles)

async def main():
    while True:
        try:
            await fetch_and_send_news()
        except Exception as e:
            print("Fetch error:", e)
        await asyncio.sleep(300)  # каждые 5 минут

if __name__ == "__main__":
    asyncio.run(main())
