import json
import os
import time
import requests
import feedparser
import openai
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from telegram import Bot

# Чтение переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=BOT_TOKEN)
openai.api_key = OPENAI_API_KEY

# RSS-ленты новостей
RSS_FEEDS = [
    "http://feeds.reuters.com/reuters/topNews",
    "http://rss.cnn.com/rss/cnn_topstories.rss",
    "https://feeds.npr.org/1001/rss.xml",
    "https://www.nbcnews.com/id/3032091/device/rss/rss.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"
]

def generate_summary(title, description):
    prompt = f"Summarize the following news story in one clear sentence:
Title: {title}
Description: {description}"
    messages = [{ "role": "user", "content": prompt }]
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=messages
    )
    return response.choices[0].message.content.strip()

def create_image_with_text(text):
    img = Image.new('RGB', (800, 400), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)
    lines = []
    line = ""
    for word in text.split():
        if len(line + word) < 60:
            line += word + " "
        else:
            lines.append(line)
            line = word + " "
    lines.append(line)
    y = 150
    for line in lines:
        draw.text((50, y), line, font=font, fill=(0, 0, 0))
        y += 40
    output = BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output

def load_sent_titles():
    if not os.path.exists("sent_titles.json"):
        return []
    with open("sent_titles.json", "r") as f:
        data = json.load(f)
        return data.get("titles", [])

def save_sent_titles(titles):
    with open("sent_titles.json", "w") as f:
        json.dump({"titles": titles}, f)

def send_news():
    sent_titles = load_sent_titles()
    new_sent = False
    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:5]:
            if entry.title in sent_titles:
                continue
            summary = generate_summary(entry.title, entry.get("description", ""))
            image = create_image_with_text(entry.title)
            bot.send_photo(chat_id=CHANNEL_ID, photo=image, caption=summary)
            sent_titles.append(entry.title)
            new_sent = True
            time.sleep(3)
    if new_sent:
        save_sent_titles(sent_titles)

if __name__ == "__main__":
    while True:
        send_news()
        time.sleep(300)
