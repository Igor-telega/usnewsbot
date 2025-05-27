import os
import asyncio
import json
import datetime
import feedparser
import requests
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from openai import OpenAI
from image_gen import generate_image
from embeddings import get_embedding, is_duplicate, save_embedding

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(bot)
client = OpenAI(api_key=OPENAI_API_KEY)

RSS_FEEDS = {
    "CNN": "http://rss.cnn.com/rss/edition.rss",
    "BBC": "http://feeds.bbci.co.uk/news/rss.xml",
    "NYT": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"
}

async def fetch_rss(feed_url):
    return feedparser.parse(feed_url)

def load_sent_titles():
    try:
        with open("sent_titles.json", "r") as f:
            return set(json.load(f))
    except FileNotFoundError:
        return set()

def save_sent_titles(titles):
    with open("sent_titles.json", "w") as f:
        json.dump(list(titles), f)

async def summarize_article(title, description, source):
    prompt = f"""Summarize the news article from {source} with the title: "{title}". Use up to 10 sentences, journalistic tone, concise yet informative, and written for an American audience. Do not add a title."""
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a professional news writer."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.6,
    )
    return response.choices[0].message.content.strip()

async def post_news():
    sent_titles = load_sent_titles()
    existing_embeddings = [get_embedding(title) for title in sent_titles]

    feeds = {name: await fetch_rss(url) for name, url in RSS_FEEDS.items()}
    items_by_index = []

    for i in range(max(len(feed.entries) for feed in feeds.values())):
        for name, feed in feeds.items():
            if i < len(feed.entries):
                items_by_index.append((name, feed.entries[i]))

    today = datetime.datetime.utcnow().date()
    for name, entry in items_by_index:
        title = entry.get("title", "")
        description = entry.get("summary", "")
        published = entry.get("published", "")
        link = entry.get("link", "")
        media_url = ""
        if "media_content" in entry:
            media_url = entry.media_content[0]["url"]

        # Check date
        try:
            pub_date = datetime.datetime(*entry.published_parsed[:6]).date()
            if (today - pub_date).days > 1:
                continue
        except:
            continue

        # Check for duplicates
        emb = get_embedding(title)
        if is_duplicate(emb, existing_embeddings):
            continue

        summary = await summarize_article(title, description, name)
        content = f"{summary}\n\n<b>Source:</b> {name}\n<b>Published:</b> {published}"

        try:
            if media_url:
                await bot.send_photo(CHANNEL_ID, photo=media_url, caption=content)
            else:
                image = generate_image(title)
                await bot.send_photo(CHANNEL_ID, photo=image, caption=content)
        except Exception as e:
            print(f"Error sending news: {e}")
            continue

        sent_titles.add(title)
        save_embedding(title, emb)
        save_sent_titles(sent_titles)
        await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(post_news())
