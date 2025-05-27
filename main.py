import os
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import InputMediaPhoto
from aiogram.enums import ParseMode
from dotenv import load_dotenv
from feedparser import parse as feedparse
from datetime import datetime, timedelta
from embeddings import get_embedding, is_duplicate, save_embedding
from image_gen import generate_image
import openai

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

RSS_FEEDS = {
    "NYT": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "BBC": "http://feeds.bbci.co.uk/news/rss.xml",
    "CNN": "http://rss.cnn.com/rss/edition.rss"
}

def get_fresh_articles():
    today = datetime.utcnow()
    yesterday = today - timedelta(days=1)
    fresh_articles = []

    for source, url in RSS_FEEDS.items():
        feed = feedparse(url)
        for entry in feed.entries:
            pub_date = None
            if hasattr(entry, 'published_parsed'):
                pub_date = datetime(*entry.published_parsed[:6])
            elif hasattr(entry, 'updated_parsed'):
                pub_date = datetime(*entry.updated_parsed[:6])

            if pub_date and pub_date > yesterday:
                fresh_articles.append({
                    "source": source,
                    "title": entry.title,
                    "link": entry.link,
                    "summary": entry.summary if hasattr(entry, 'summary') else '',
                    "published": pub_date
                })

    # Сортируем по дате, затем группируем по источникам, чередуем
    grouped = {src: [] for src in RSS_FEEDS}
    for article in fresh_articles:
        grouped[article['source']].append(article)

    final = []
    while any(grouped.values()):
        for src in grouped:
            if grouped[src]:
                final.append(grouped[src].pop(0))

    return final

async def summarize_article(title, summary, source):
    prompt = f"""Summarize the news article from {source} with the title:
\"{title}\"
Summary:
{summary}

Keep it neutral and journalistic. Expand to 8–10 sentences. Output in English for American audience.
"""
    response = await openai.ChatCompletion.acreate(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    return response.choices[0].message.content.strip()

async def post_to_channel(article):
    title = article['title']
    link = article['link']
    source = article['source']
    summary = article['summary']
    published = article['published'].strftime("%a, %d %b %Y %H:%M:%S GMT")

    embedding = get_embedding(title)
    if is_duplicate(embedding, "embeddings_storage.py"):
        print("DUPLICATE:", title)
        return

    save_embedding(title, embedding)

    try:
        summarized = await summarize_article(title, summary, source)
        prompt = f"{title}. {summarized}"
        image_url = generate_image(prompt)
    except Exception as e:
        print("Error with summary/image:", e)
        return

    content = f"<b>{title}</b>\n\n{summarized}\n\nSource: {source}\nPublished: {published}\n\n#News #{source}"
    try:
        await bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=image_url,
            caption=content,
            parse_mode=ParseMode.HTML
        )
        print("Posted:", title)
    except Exception as e:
        print("Post error:", e)

async def main():
    articles = get_fresh_articles()
    for article in articles:
        await post_to_channel(article)
        await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())

