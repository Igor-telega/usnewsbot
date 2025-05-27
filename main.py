import os
import asyncio
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
import feedparser
import openai
from embeddings import get_embedding, is_duplicate, save_embedding
from image_gen import generate_image

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

SOURCES = [
    {"name": "NYT", "url": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"},
    {"name": "BBC", "url": "http://feeds.bbci.co.uk/news/rss.xml"},
    {"name": "CNN", "url": "http://rss.cnn.com/rss/edition.rss"}
]

SENT_TITLES_FILE = "sent_titles.json"
POST_LIMIT = 5

def load_sent_titles():
    if os.path.exists(SENT_TITLES_FILE):
        with open(SENT_TITLES_FILE, "r") as f:
            return json.load(f)
    return {}

def save_sent_titles(titles):
    with open(SENT_TITLES_FILE, "w") as f:
        json.dump(titles, f)

async def summarize_article(title, description, source):
    prompt = (
        f"Summarize the news article from {source} with the title: '{title}'.\n\n"
        f"Description: {description}\n\n"
        "Keep the summary journalistic, neutral in tone, and concise — around 10 sentences max. "
        "Target it for an American audience. Do not include the original title. Do not add hashtags."
    )

    response = await openai.ChatCompletion.acreate(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

async def send_news():
    sent_titles = load_sent_titles()
    new_titles = {}

    feeds = {s["name"]: feedparser.parse(s["url"]).entries for s in SOURCES}
    grouped = list(zip(*(feeds[src["name"]] for src in SOURCES)))

    posts_sent = 0
    for group in grouped:
        for i, article in enumerate(group):
            source = SOURCES[i]["name"]
            title = article.title
            description = article.get("description", "")
            published = article.get("published_parsed")
            image_url = article.get("media_content", [{}])[0].get("url")

            if not title or not published:
                continue

            pub_date = datetime(*published[:6])
            if pub_date < datetime.utcnow() - timedelta(days=1):
                continue

            new_titles.setdefault(source, [])

            embedding = get_embedding(title)
            if is_duplicate(embedding, sent_titles.get(source, [])):
                continue

            summary = await summarize_article(title, description, source)
            content = f"<b>{source}</b>\n\n{summary}\n\nPublished: {pub_date.strftime('%Y-%m-%d %H:%M UTC')}"
            photo_url = image_url if image_url else generate_image(summary)

            await bot.send_photo(chat_id=CHANNEL_ID, photo=photo_url, caption=content)
            new_titles[source].append(embedding)
            posts_sent += 1

            if posts_sent >= POST_LIMIT:
                save_sent_titles(new_titles)
                return

    save_sent_titles(new_titles)

async def main():
    await send_news()

if __name__ == "__main__":
    asyncio.run(main())
