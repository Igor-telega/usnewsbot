import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
import requests
import openai
from dotenv import load_dotenv
from feedparser import parse
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.types import InputFile
from embeddings import get_embedding, is_duplicate, save_embedding
from image_gen import generate_image

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=BOT_TOKEN, default=ParseMode.HTML)
dp = Dispatcher()

openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)

logging.basicConfig(level=logging.INFO)

rss_feeds = {
    "NY Times": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "Reuters": "http://feeds.reuters.com/reuters/topNews",
    "CNN": "http://rss.cnn.com/rss/cnn_topstories.rss",
    "AP": "https://apnews.com/rss",
    "The Guardian": "https://www.theguardian.com/world/rss",
    "NPR": "https://feeds.npr.org/1001/rss.xml"
}

MAX_TOTAL_POSTS = 5

def load_sent_titles():
    try:
        with open("sent_titles.json", "r") as f:
            return json.load(f)["titles"]
    except FileNotFoundError:
        return []

def save_sent_titles(titles):
    with open("sent_titles.json", "w") as f:
        json.dump({"titles": titles}, f)

async def summarize_article(title, content, source):
    try:
        messages = [
            {"role": "system", "content": "Ты профессиональный американский новостной редактор. Пиши кратко, понятно, информативно, в 5-10 предложениях. Без ссылок. Без призывов."},
            {"role": "user", "content": f"Сделай краткое журналистское описание новости под названием '{title}' из источника {source}. Вот содержание:\n\n{content}"}
        ]
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"Error summarizing article: {e}")
        return None

async def post_to_channel(article):
    title = article["title"]
    summary = await summarize_article(title, article.get("summary", ""), article["source"])
    if not summary:
        return

    embedding = get_embedding(summary)
    if is_duplicate(embedding, "embeddings_storage.py"):
        return

    save_embedding(title, embedding)

    published_date = article["published"].strftime("%B %d, %Y %H:%M")
    content = f"<b>{title}</b>\n\n{summary}\n\n<i>{article['source']} — {published_date}</i>"

    image_url = None
    try:
        image_url = generate_image(title)
    except Exception as e:
        logging.error(f"Error generating image: {e}")

    try:
        if image_url:
            img_data = requests.get(image_url).content
            with open("temp.jpg", "wb") as f:
                f.write(img_data)
            await bot.send_photo(chat_id=CHANNEL_ID, photo=InputFile("temp.jpg"), caption=content)
            os.remove("temp.jpg")
        else:
            await bot.send_message(chat_id=CHANNEL_ID, text=content)
    except Exception as e:
        logging.error(f"Error posting to Telegram: {e}")

async def main():
    sent_titles = load_sent_titles()
    articles_by_source = {source: [] for source in rss_feeds}
    now = datetime.utcnow()
    time_limit = now - timedelta(hours=10)

    # Сбор свежих новостей
    for source, url in rss_feeds.items():
        feed = parse(url)
        for entry in feed.entries:
            pub_time = entry.get("published_parsed")
            if not pub_time:
                continue
            published_dt = datetime(*pub_time[:6])
            if published_dt < time_limit:
                continue
            if entry.title in sent_titles:
                continue
            articles_by_source[source].append({
                "title": entry.title,
                "summary": entry.get("summary", ""),
                "link": entry.link,
                "source": source,
                "published": published_dt
            })

    # Чередование по источникам
    combined = []
    max_len = max(len(arts) for arts in articles_by_source.values())
    for i in range(max_len):
        for source in rss_feeds:
            if i < len(articles_by_source[source]):
                combined.append(articles_by_source[source][i])
            if len(combined) >= MAX_TOTAL_POSTS:
                break
        if len(combined) >= MAX_TOTAL_POSTS:
            break

    for article in combined:
        await post_to_channel(article)
        sent_titles.append(article["title"])
        await asyncio.sleep(5)

    save_sent_titles(sent_titles)

if __name__ == "__main__":
    asyncio.run(main())
