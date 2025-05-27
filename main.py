import os
import asyncio
import json
from datetime import datetime, timedelta

import aiohttp
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from feedparser import parse
from openai import OpenAI
from embeddings import get_embedding, is_duplicate, save_embedding
from image_gen import generate_image

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

client = OpenAI(api_key=OPENAI_API_KEY)

RSS_FEEDS = {
    "NYT": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "BBC": "http://feeds.bbci.co.uk/news/rss.xml",
    "CNN": "http://rss.cnn.com/rss/edition.rss"
}

def parse_feed(url):
    return parse(url).entries

def extract_articles(feeds):
    articles_by_source = {}
    yesterday = datetime.utcnow() - timedelta(days=1)

    for source, url in feeds.items():
        entries = parse_feed(url)
        filtered = []
        for entry in entries:
            try:
                published = datetime(*entry.published_parsed[:6])
            except Exception:
                continue
            if published < yesterday:
                continue
            filtered.append({
                "source": source,
                "title": entry.title,
                "link": entry.link,
                "published": published.strftime("%a, %d %b %Y %H:%M:%S GMT"),
                "summary": entry.summary
            })
        articles_by_source[source] = filtered
    return articles_by_source

def interleave_articles(articles_by_source, max_count=5):
    all_sources = list(articles_by_source.keys())
    interleaved = []
    for i in range(max_count):
        for source in all_sources:
            if i < len(articles_by_source[source]):
                interleaved.append(articles_by_source[source][i])
    return interleaved[:max_count]

async def summarize_article(title, summary):
    prompt = (
        f"Title: {title}\n"
        f"Summary: {summary}\n\n"
        "Write a short, journalistic news post of about 10 sentences for a Telegram channel. "
        "Keep it neutral and journalistic. Don't use HTML formatting or emojis. "
        "Do not include links. End with hashtags based on the topic."
    )

    completion = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a news editor writing for an American audience."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )

    return completion.choices[0].message.content.strip()

async def send_article(article, sent_titles):
    embedding = get_embedding(article["title"])
    if is_duplicate(embedding, sent_titles):
        return
    summary = await summarize_article(article["title"], article["summary"])
    image_url = await generate_image(article["title"])

    text = (
        f"<b>{article['title']}</b>\n\n"
        f"{summary}\n\n"
        f"<i>Source:</i> {article['source']}\n"
        f"<i>Published:</i> {article['published']}"
    )

    try:
        await bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=image_url,
            caption=text,
            parse_mode=ParseMode.HTML
        )
        save_embedding(article["title"], embedding)
        await asyncio.sleep(5)
    except Exception as e:
        print(f"Failed to send article: {e}")

async def main():
    try:
        with open("sent_titles.json", "r") as f:
            sent_titles = json.load(f)
    except FileNotFoundError:
        sent_titles = []

    articles_by_source = extract_articles(RSS_FEEDS)
    articles = interleave_articles(articles_by_source)

    for article in articles:
        await send_article(article, sent_titles)

    with open("sent_titles.json", "w") as f:
        json.dump(sent_titles, f)

if __name__ == "__main__":
    asyncio.run(main())
