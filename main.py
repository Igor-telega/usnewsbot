import asyncio
import os
import feedparser
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.types import InputFile
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import openai
import json
from embeddings import get_embedding, is_duplicate, save_embedding
from image_gen import generate_image

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


def extract_hashtags(text):
    keywords = [word.strip("#,.!?").capitalize() for word in text.split() if len(word) > 4]
    tags = list({f"#{kw}" for kw in keywords[:3]})
    return " ".join(tags) if tags else "#News"


def extract_date(entry):
    try:
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
            published = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
        else:
            return None
        return published.astimezone().strftime("%Y-%m-%d")
    except Exception:
        return None


async def summarize_text(title, text):
    prompt = (
        "Summarize the following news article into a short but informative 8-10 sentence brief, "
        "suitable for a professional American audience. Write in a neutral journalistic tone, as if it were published "
        "by a major news outlet. Do not include the original headline.\n\n"
        f"Title: {title}\n\nContent: {text}"
    )

    response = await openai.ChatCompletion.acreate(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a news editor."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content.strip()


async def fetch_and_send_news():
    sent_titles = load_sent_titles()
    new_titles = []
    feed_items = []

    for source, url in RSS_FEEDS.items():
        feed = feedparser.parse(url)
        for entry in feed.entries[:10]:
            feed_items.append((source, entry))

    # Перемешиваем порядок: NYT → CNN → Reuters → NYT...
    grouped = {}
    for source, entry in feed_items:
        grouped.setdefault(source, []).append(entry)
    combined = []
    for i in range(10):
        for source in RSS_FEEDS:
            if i < len(grouped.get(source, [])):
                combined.append((source, grouped[source][i]))

    count = 0
    for source, entry in combined:
        if entry.title in sent_titles:
            continue

        pub_date = extract_date(entry)
        if pub_date:
            published_dt = datetime.strptime(pub_date, "%Y-%m-%d")
            if datetime.now() - published_dt > timedelta(days=1):
                continue

        summary = entry.summary if hasattr(entry, "summary") else ""
        full_text = f"{entry.title}\n\n{summary}"
        embedding = get_embedding(full_text)
        if is_duplicate(embedding):
            continue

        summarized = await summarize_text(entry.title, summary)
        hashtags = extract_hashtags(summarized)
        message = f"<b>{entry.title}</b>\n\n{summarized}\n\n<i>{source} | {pub_date}</i>\n{hashtags}"

        image_url = None
        if "media_content" in entry and entry.media_content:
            image_url = entry.media_content[0].get("url")

        try:
            if image_url:
                image_data = requests.get(image_url).content
                with open("temp.jpg", "wb") as f:
                    f.write(image_data)
                photo = InputFile("temp.jpg")
                await bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=message)
                os.remove("temp.jpg")
            else:
                img_path = await generate_image(entry.title)
                photo = InputFile(img_path)
                await bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=message)
                os.remove(img_path)
        except Exception as e:
            print(f"Error sending message: {e}")
            continue

        save_embedding(entry.title, embedding)
        new_titles.append(entry.title)
        count += 1
        if count >= MAX_POSTS_PER_RUN:
            break

    save_sent_titles(sent_titles + new_titles)


async def main():
    while True:
        try:
            await fetch_and_send_news()
        except Exception as e:
            print(f"Error: {e}")
        await asyncio.sleep(300)


if __name__ == "__main__":
    asyncio.run(main())
