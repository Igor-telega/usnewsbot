import os
import json
import time
import feedparser
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import InputMediaPhoto
from dotenv import load_dotenv
from embeddings_storage import is_duplicate, save_embedding
from openai import OpenAI
import tiktoken

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(bot)
client = OpenAI(api_key=OPENAI_API_KEY)

sent_titles_path = "sent_titles.json"
MAX_NEWS_PER_CYCLE = 5

def load_sent_titles():
    if not os.path.exists(sent_titles_path):
        return []
    with open(sent_titles_path, "r") as file:
        return json.load(file)

def save_sent_titles(titles):
    with open(sent_titles_path, "w") as file:
        json.dump(titles, file)

def get_embedding(text):
    response = client.embeddings.create(input=[text], model="text-embedding-3-small")
    return response.data[0].embedding

def summarize(text):
    prompt = f"Summarize this news article in 2-3 sentences for a Telegram post:\n\n{text}"
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=200
    )
    return response.choices[0].message.content.strip()

async def send_news(title, summary, published, source, image_url=None, hashtags=""):
    message = f"<b>{title}</b>\n\n{summary}\n\n<em>Published:</em> {published}\n<em>Source:</em> {source}\n{hashtags}"
    try:
        if image_url:
            await bot.send_photo(chat_id=CHANNEL_ID, photo=image_url, caption=message, parse_mode="HTML")
        else:
            await bot.send_message(chat_id=CHANNEL_ID, text=message, parse_mode="HTML")
    except Exception as e:
        print("Error sending message:", e)

def extract_hashtags(text, limit=3):
    words = text.split()
    tags = [word.strip(".,!?").capitalize() for word in words if len(word) > 4]
    hashtags = list(dict.fromkeys(tags))[:limit]
    return " ".join(f"#{tag}" for tag in hashtags)

async def check_and_send_news():
    feeds = [
        "https://rss.nytimes.com/services/xml/rss/nyt/US.xml",
        "http://feeds.bbci.co.uk/news/world/rss.xml",
        "https://rss.cnn.com/rss/edition.rss"
    ]
    sent_titles = load_sent_titles()
    new_sent_titles = []
    count = 0

    for url in feeds:
        if count >= MAX_NEWS_PER_CYCLE:
            break
        feed = feedparser.parse(url)
        for entry in feed.entries:
            if count >= MAX_NEWS_PER_CYCLE:
                break
            title = entry.title.strip()
            if title in sent_titles or any(title in t for t in new_sent_titles):
                continue
            summary_text = entry.get("summary", "")[:1500]
            source = feed.feed.get("title", "News")
            published = entry.get("published", "No date")
            image_url = None
            if "media_content" in entry:
                image_url = entry.media_content[0].get("url")
            embedding = get_embedding(title)
            if is_duplicate(embedding):
                continue
            summary = summarize(summary_text)
            hashtags = extract_hashtags(title)
            await send_news(title, summary, published, source, image_url, hashtags)
            save_embedding(title, embedding)
            new_sent_titles.append(title)
            count += 1
            await asyncio.sleep(1)

    sent_titles = (sent_titles + new_sent_titles)[-100:]
    save_sent_titles(sent_titles)

async def scheduler():
    while True:
        await check_and_send_news()
        await asyncio.sleep(60)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(scheduler())
    loop.run_forever()
