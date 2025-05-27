import os
import asyncio
import feedparser
import requests
import json
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from openai import OpenAI
from embeddings import get_embedding, is_duplicate, save_embedding
from image_gen import generate_image

BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()
openai = OpenAI(api_key=OPENAI_API_KEY)

sources = {
    "CNN": "http://rss.cnn.com/rss/edition.rss",
    "NYT": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "BBC": "http://feeds.bbci.co.uk/news/rss.xml",
}

sent_titles_file = "sent_titles.json"
if os.path.exists(sent_titles_file):
    with open(sent_titles_file, "r") as f:
        sent_titles = set(json.load(f))
else:
    sent_titles = set()

def save_sent_titles():
    with open(sent_titles_file, "w") as f:
        json.dump(list(sent_titles), f)

def get_recent_entries():
    recent_entries = []
    cutoff_time = datetime.utcnow() - timedelta(days=1)

    for source, url in sources.items():
        feed = feedparser.parse(url)
        for entry in feed.entries:
            if hasattr(entry, "published_parsed"):
                published = datetime(*entry.published_parsed[:6])
                if published >= cutoff_time:
                    recent_entries.append((source, entry))
    return recent_entries

async def summarize_and_post():
    entries_by_index = list(zip(*[[(i, source, entry) for i, (source, entry) in enumerate(get_recent_entries()) if source_name == source] for source_name in sources]))[0]

    for group in zip(*entries_by_index):
        for _, source, entry in group:
            title = entry.title.strip()

            if title in sent_titles:
                continue

            full_text = entry.get("summary", "")
            prompt = f"Summarize the news article from {source} with the title: '{title}'. Keep it neutral and journalistic. Limit to 8-10 sentences. Do not repeat the title."

            response = openai.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a professional news editor for an American audience."},
                    {"role": "user", "content": prompt}
                ]
            )

            summary = response.choices[0].message.content.strip()
            embedding = get_embedding(summary)

            if is_duplicate(embedding, []):  # optionally load existing embeddings
                continue

            save_embedding(title, embedding)
            sent_titles.add(title)
            save_sent_titles()

            image = generate_image(title)
            caption = f"<b>{title}</b>\n\n{summary}\n\n<code>Source: {source}</code>"
            await bot.send_photo(chat_id=CHANNEL_ID, photo=image, caption=caption)

async def main():
    await summarize_and_post()

if __name__ == "__main__":
    asyncio.run(main())
