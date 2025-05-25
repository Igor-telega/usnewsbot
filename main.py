import requests
import feedparser
import json
import time
import os
import openai
from PIL import Image
from io import BytesIO
from telegram import Bot

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=BOT_TOKEN)
openai.api_key = OPENAI_API_KEY

rss_feeds = [
    "http://feeds.reuters.com/reuters/topNews",
    "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "https://www.cbsnews.com/latest/rss/main",
    "https://feeds.a.dj.com/rss/RSSWorldNews.xml",
    "https://www.npr.org/rss/rss.php?id=1001"
]

try:
    with open("sent_titles.json", "r") as file:
        sent_titles = json.load(file)
except FileNotFoundError:
    sent_titles = []

def generate_summary(title, description):
    prompt = f"Summarize the following news in 1-2 sentences for a Telegram post:\n\nTitle: {title}\n\nContent: {description}"
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{{ "role": "user", "content": prompt }}],
        max_tokens=60,
        temperature=0.7
    )
    return response.choices[0].message.content.strip()

def send_news():
    for feed_url in rss_feeds:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            title = entry.title
            if title in sent_titles:
                continue

            summary = entry.summary if 'summary' in entry else ""
            summary_text = generate_summary(title, summary)

            message = f"<b>{title}</b>\n\n{summary_text}"

            if "media_content" in entry and entry.media_content:
                image_url = entry.media_content[0]["url"]
                response = requests.get(image_url)
                image = BytesIO(response.content)
                bot.send_photo(chat_id=CHANNEL_ID, photo=image, caption=message, parse_mode="HTML")
            else:
                bot.send_message(chat_id=CHANNEL_ID, text=message, parse_mode="HTML")

            sent_titles.append(title)
            with open("sent_titles.json", "w") as file:
                json.dump(sent_titles, file)

        time.sleep(5)

while True:
    send_news()
    time.sleep(300)
