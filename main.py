import os
import json
import asyncio
import feedparser
import requests
from datetime import datetime
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from openai import OpenAI
import tiktoken

from embeddings_storage import is_duplicate, save_embedding

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

client = OpenAI(api_key=OPENAI_API_KEY)

SOURCES = [
    ("https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml", "NYT"),
    ("http://feeds.bbci.co.uk/news/rss.xml", "BBC News"),
    ("http://rss.cnn.com/rss/cnn_topstories.rss", "CNN.com"),
]

MAX_NEWS_PER_RUN = 5
SENT_TITLES_FILE = "sent_titles.json"

def load_sent_titles():
    if not os.path.exists(SENT_TITLES_FILE):
        return []
    with open(SENT_TITLES_FILE, "r") as f:
        return json.load(f)

def save_sent_titles(titles):
    with open(SENT_TITLES_FILE, "w") as f:
        json.dump(titles[-100:], f)

def extract_hashtags(title):
    words = title.split()
    hashtags = []
    for word in words:
        clean = word.strip(".,!?")
        if clean.istitle() and len(clean) > 3:
            hashtags.append(f"#{clean}")
    return " ".join(hashtags)

async def summarize_article(title, description):
    prompt = (
        f"Summarize this news article for an American audience in a professional tone. "
        f"The summary should capture the key message in **7–10 sentences**.\n\n"
        f"Title: {title}\n\nDescription: {description}"
    )

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a news editor summarizing breaking news for an English-speaking audience."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )

    return response.choices[0].message.content.strip()

async def send_news():
    sent_titles = load_sent_titles()
    count = 0

    for url, source_name in SOURCES:
        feed = feedparser.parse(url)

        for entry in feed.entries:
            if count >= MAX_NEWS_PER_RUN:
                return

            title = entry.get("title", "")
            if title in sent_titles:
                continue

            description = entry.get("summary", "")[:1000]
            summary = await summarize_article(title, description)

            full_text = (
                f"<b>{title}</b>\n\n"
                f"{summary}\n\n"
                f"<i>Source:</i> {source_name}\n"
                f"<i>Published:</i> {entry.get('published', 'Unknown')}\n"
                f"{extract_hashtags(title)}"
            )

            try:
                embedding_response = client.embeddings.create(
                    model="text-embedding-ada-002",
                    input=title
                )
                embedding = embedding_response.data[0].embedding

                if is_duplicate(embedding):
                    continue

                save_embedding(title, embedding)
                await bot.send_message(CHANNEL_ID, full_text, parse_mode="HTML")
                sent_titles.append(title)
                count += 1

            except Exception as e:
                print(f"Error sending message: {e}")
                continue

    save_sent_titles(sent_titles)

if __name__ == "__main__":
    asyncio.run(send_news())
