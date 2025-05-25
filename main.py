import json
import feedparser
import openai
import os
import asyncio
from telegram import Bot
from PIL import Image
import requests
from io import BytesIO

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

openai.api_key = OPENAI_API_KEY
bot = Bot(token=BOT_TOKEN)

RSS_FEEDS = [
    "http://rss.cnn.com/rss/edition.rss",
    "http://feeds.bbci.co.uk/news/rss.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "https://feeds.a.dj.com/rss/RSSWorldNews.xml",
    "https://www.reutersagency.com/feed/?best-topics=top-news&post_type=best"
]

SENT_TITLES_FILE = "sent_titles.json"

def load_sent_titles():
    try:
        with open(SENT_TITLES_FILE, "r") as f:
            return set(json.load(f)["titles"])
    except Exception:
        return set()

def save_sent_titles(titles):
    with open(SENT_TITLES_FILE, "w") as f:
        json.dump({"titles": list(titles)}, f)

def summarize_text(title, content):
    prompt = f"Summarize the following news story in one clear sentence:\nTitle: {title}\nContent: {content}"
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message["content"].strip()

async def send_news():
    sent_titles = load_sent_titles()
    new_titles = set()

    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            title = entry.title.strip()
            if title in sent_titles or title in new_titles:
                continue

            content = entry.get("summary", "")
            summary = summarize_text(title, content)

            image_url = ""
            if "media_content" in entry:
                image_url = entry.media_content[0].get("url", "")
            elif "links" in entry:
                for link in entry.links:
                    if link.get("type", "").startswith("image"):
                        image_url = link.get("href", "")
                        break

            try:
                if image_url:
                    response = requests.get(image_url)
                    image = BytesIO(response.content)
                    await bot.send_photo(chat_id=CHANNEL_ID, photo=image, caption=f"{title}\n\n{summary}")
                else:
                    await bot.send_message(chat_id=CHANNEL_ID, text=f"{title}\n\n{summary}")
                new_titles.add(title)
            except Exception as e:
                print(f"Error sending message: {e}")

    if new_titles:
        save_sent_titles(sent_titles.union(new_titles))

if __name__ == "__main__":
    asyncio.run(send_news())
