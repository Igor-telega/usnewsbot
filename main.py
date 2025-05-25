import json
import os
import time
import feedparser
import requests
from PIL import Image
from io import BytesIO
from telegram import Bot
from openai import OpenAI

bot_token = os.getenv("BOT_TOKEN")
channel_id = os.getenv("CHANNEL_ID")
openai_api_key = os.getenv("OPENAI_API_KEY")

bot = Bot(token=bot_token)
client = OpenAI(api_key=openai_api_key)

RSS_FEEDS = [
    "http://feeds.reuters.com/reuters/topNews",
    "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "https://feeds.a.dj.com/rss/RSSWorldNews.xml",
    "https://www.politico.com/rss/politics08.xml",
    "https://www.npr.org/rss/rss.php?id=1001"
]

DATA_FILE = "sent_titles.json"

def load_sent_titles():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
    return data.get("titles", [])

def save_sent_titles(titles):
    with open(DATA_FILE, "w") as f:
        json.dump({"titles": titles[-200:]}, f)

def generate_summary(title, description):
    prompt = f"Summarize the following news story in one clear sentence:\nTitle: {title}\nDescription: {description}"
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=60,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return title

def fetch_image(url):
    try:
        response = requests.get(url)
        image = Image.open(BytesIO(response.content))
        path = "/tmp/temp.jpg"
        image.save(path)
        return path
    except:
        return None

def send_news():
    sent_titles = load_sent_titles()
    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:5]:
            title = entry.get("title", "")
            if title in sent_titles:
                continue
            summary = generate_summary(title, entry.get("description", ""))
            image_url = entry.get("media_content", [{}])[0].get("url") if "media_content" in entry else None
            image_path = fetch_image(image_url) if image_url else None
            try:
                if image_path:
                    with open(image_path, "rb") as photo:
                        bot.send_photo(chat_id=channel_id, photo=photo, caption=f"{title}\n\n{summary}")
                else:
                    bot.send_message(chat_id=channel_id, text=f"{title}\n\n{summary}")
                sent_titles.append(title)
                save_sent_titles(sent_titles)
                time.sleep(2)
            except Exception as e:
                continue

if __name__ == "__main__":
    send_news()
