import asyncio
import os
import random
import json
from datetime import datetime, timedelta

import requests
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from feedparser import parse
from openai import OpenAI
from embeddings import get_embedding, is_duplicate, save_embedding
from image_gen import generate_image

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai = OpenAI(api_key=OPENAI_API_KEY)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

NEWS_LIMIT = 5
DAYS_LIMIT = 1

sent_titles_path = "sent_titles.json"
if os.path.exists(sent_titles_path):
    with open(sent_titles_path, "r") as f:
        sent_titles = json.load(f)
else:
    sent_titles = []

def fetch_feeds():
    feeds = {
        "NYT": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
        "CNN": "http://rss.cnn.com/rss/cnn_topstories.rss",
        "BBC": "http://feeds.bbci.co.uk/news/rss.xml",
    }
    now = datetime.utcnow()
    articles_by_source = {key: [] for key in feeds}
    for source, url in feeds.items():
        feed = parse(url)
        for entry in feed.entries:
            published = entry.get("published_parsed") or entry.get("updated_parsed")
            if not published:
                continue
            published_dt = datetime(*published[:6])
            if (now - published_dt) <= timedelta(days=DAYS_LIMIT):
                articles_by_source[source].append({
                    "title": entry.title,
                    "summary": entry.summary,
                    "link": entry.link,
                    "published": published_dt.strftime("%a, %d %b %Y %H:%M:%S GMT"),
                    "source": source
                })
    return articles_by_source

async def generate_caption(article):
    prompt = (
        f"Write a professional 10-sentence summary of this news article for an American audience. "
        f"Keep it neutral and journalistic.

Title: {article['title']}

Summary: {article['summary']}"
    )
    response = openai.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

async def send_news():
    articles_by_source = fetch_feeds()
    max_articles = max(len(lst) for lst in articles_by_source.values())
    selected_articles = []

    for i in range(max_articles):
        for source in articles_by_source:
            if i < len(articles_by_source[source]):
                selected_articles.append(articles_by_source[source][i])
            if len(selected_articles) >= NEWS_LIMIT:
                break
        if len(selected_articles) >= NEWS_LIMIT:
            break

    for article in selected_articles:
        if article["title"] in sent_titles:
            continue
        embedding = get_embedding(article["title"])
        if is_duplicate(embedding, [get_embedding(t) for t in sent_titles]):
            continue

        caption = await generate_caption(article)
        tags = " ".join(f"#{word.strip('.').capitalize()}" for word in article["title"].split() if word.istitle() and len(word) > 3)
        full_caption = f"<b>{article['title']}</b>

{caption}

"                        f"<b>Source:</b> {article['source']}
"                        f"<b>Published:</b> {article['published']}

{tags}"

        image = generate_image(article["title"])
        await bot.send_photo(chat_id=int(CHANNEL_ID), photo=image, caption=full_caption, parse_mode=ParseMode.HTML)

        sent_titles.append(article["title"])
        save_embedding(article["title"], embedding)

        with open(sent_titles_path, "w") as f:
            json.dump(sent_titles, f)

async def main():
    await send_news()

if __name__ == "__main__":
    asyncio.run(main())
