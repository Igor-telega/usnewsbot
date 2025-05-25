import os
import json
import time
import feedparser
import requests
from PIL import Image
from io import BytesIO
import openai
from telegram import Bot

# Переменные окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=BOT_TOKEN)
openai.api_key = OPENAI_API_KEY

# Список источников
RSS_FEEDS = [
    "http://rss.cnn.com/rss/cnn_topstories.rss",
    "http://feeds.bbci.co.uk/news/rss.xml",
    "https://www.reutersagency.com/feed/?best-topics=top-news"
]

# Файл с заголовками отправленных новостей
SENT_TITLES_FILE = "sent_titles.json"

def load_sent_titles():
    if os.path.exists(SENT_TITLES_FILE):
        with open(SENT_TITLES_FILE, "r") as file:
            data = json.load(file)
            return set(data.get("titles", []))
    return set()

def save_sent_titles(titles):
    with open(SENT_TITLES_FILE, "w") as file:
        json.dump({"titles": list(titles)}, file)

def generate_summary(title, content):
    prompt = f"Summarize the following news in one short sentence: {title} - {content}"
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )
    return response.choices[0].message["content"].strip()

def get_image_url(entry):
    media = entry.get("media_content", [])
    if media and isinstance(media, list):
        return media[0].get("url")
    return None

def send_news():
    sent_titles = load_sent_titles()

    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            title = entry.get("title", "")
            if title in sent_titles:
                continue

            summary = entry.get("summary", "")
            image_url = get_image_url(entry)

            try:
                summary_text = generate_summary(title, summary)
                caption = f"{title}\n\n{summary_text}"

                if image_url:
                    response = requests.get(image_url)
                    image = Image.open(BytesIO(response.content))
                    image.save("temp.jpg")
                    with open("temp.jpg", "rb") as photo:
                        bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=caption)
                else:
                    bot.send_message(chat_id=CHANNEL_ID, text=caption)

                sent_titles.add(title)
                save_sent_titles(sent_titles)
                time.sleep(3)

            except Exception as e:
                print(f"Error sending news: {e}")

if __name__ == "__main__":
    send_news()
