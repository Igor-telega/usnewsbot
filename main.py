import asyncio
import logging
import os
import feedparser
import requests
from aiogram import Bot
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
import json

import sys
import time

BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHANNEL_ID = os.environ.get('CHANNEL_ID')
bot = Bot(token=BOT_TOKEN)

FEEDS = [
    "http://rss.cnn.com/rss/edition.rss",
    "http://feeds.reuters.com/Reuters/domesticNews",
    "http://feeds.bbci.co.uk/news/rss.xml",
    "http://feeds.foxnews.com/foxnews/latest",
    "https://www.npr.org/rss/rss.php?id=1001"
]

POSTED_URLS_FILE = 'sent_urls.json'
CHECK_INTERVAL = 300  # 5 минут
POST_WINDOW = 2  # часы, сколько времени считаем новость "свежей"

posted_urls = set()

def load_posted_urls():
    if os.path.exists(POSTED_URLS_FILE):
        with open(POSTED_URLS_FILE, 'r') as f:
            return set(json.load(f))
    return set()

def save_posted_urls(posted_urls):
    with open(POSTED_URLS_FILE, 'w') as f:
        json.dump(list(posted_urls), f)

def create_title_image(text, output_path="headline.png"):
    width, height = 1024, 512
    background = (0, 0, 0)
    text_color = (255, 255, 255)

    image = Image.new('RGB', (width, height), background)
    draw = ImageDraw.Draw(image)

    try:
        font = ImageFont.truetype("arial.ttf", 44)
    except:
        font = ImageFont.load_default()

    words = text.split()
    lines = []
    line = ''
    for word in words:
        test_line = line + word + ' '
        if draw.textlength(test_line, font=font) < width - 80:
            line = test_line
        else:
            lines.append(line)
            line = word + ' '
    lines.append(line)

    y = height // 2 - (len(lines) * 30)
    for line in lines:
        draw.text((50, y), line.strip(), fill=text_color, font=font)
        y += 50

    image.save(output_path)
    return output_path

def fetch_news():
    articles = []
    for feed_url in FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            published = entry.get("published_parsed")
            if published:
                pub_date = datetime.fromtimestamp(time.mktime(published))
                if datetime.utcnow() - pub_date > timedelta(hours=POST_WINDOW):
                    continue
            url = entry.get("link")
            if url and url not in posted_urls:
                articles.append({
                    "title": entry.get("title", ""),
                    "summary": entry.get("summary", ""),
                    "url": url,
                    "image": entry.get("media_content", [{}])[0].get("url", None)
                })
    return articles

async def send_article(article):
    try:
        url = article['url']
        title = article['title']
        summary = article.get('summary', '')
        image_url = article.get('image')

        if url in posted_urls:
            return

        posted_urls.add(url)
        save_posted_urls(posted_urls)

        text = f"<b>{title}</b>\n\n{summary.strip()}" if summary else f"<b>{title}</b>"

        if image_url:
            await bot.send_photo(chat_id=CHANNEL_ID, photo=image_url, caption=text, parse_mode='HTML')
        else:
            image_path = create_title_image(title)
            with open(image_path, 'rb') as photo:
                await bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=text, parse_mode='HTML')

        print(f"Отправлено: {title}")

    except Exception as e:
        logging.exception(f"Ошибка при отправке статьи: {e}")

async def news_loop():
    global posted_urls
    posted_urls = load_posted_urls()
    print("Бот запущен...")
    while True:
        articles = fetch_news()
        print(f"Найдено {len(articles)} свежих новостей")
        for article in articles:
            await send_article(article)
        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    asyncio.run(news_loop())
