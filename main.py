import json
import logging
import asyncio
import feedparser
import openai
import os
from aiogram import Bot, types
from aiogram.types import URLInputFile
from datetime import datetime
import time

# Настройки
openai.api_key = os.getenv("OPENAI_API_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = "@usnewsdailytestchannel"

# RSS-источники
RSS_FEEDS = [
    "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "http://feeds.bbci.co.uk/news/rss.xml",
    "http://rss.cnn.com/rss/cnn_topstories.rss",
    "https://feeds.npr.org/1001/rss.xml",
    "https://www.reutersagency.com/feed/?best-topics=top-news&post_type=best",
    "https://www.theguardian.com/world/rss"
]

# Ограничения
POST_LIMIT = 5
SUMMARY_PROMPT = "Summarize this news article in 2-4 sentences as a news brief for Telegram:\n\n"

# Инициализация бота
bot = Bot(token=BOT_TOKEN, parse_mode=types.ParseMode.HTML)

# Загрузка опубликованных заголовков
if os.path.exists("sent_titles.json"):
    with open("sent_titles.json", "r") as f:
        sent_titles = json.load(f).get("titles", [])
else:
    sent_titles = []

# Сохранение новых заголовков
def save_titles():
    with open("sent_titles.json", "w") as f:
        json.dump({"titles": sent_titles}, f)

# Генерация краткого текста через OpenAI
async def summarize_article(text):
    try:
        response = await openai.ChatCompletion.acreate(
            model="gpt-4",
            messages=[{"role": "user", "content": SUMMARY_PROMPT + text}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"OpenAI error: {e}")
        return None

# Получение и публикация новостей
async def fetch_and_post():
    posted = 0
    for feed_url in RSS_FEEDS:
        if posted >= POST_LIMIT:
            break
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            if posted >= POST_LIMIT:
                break
            title = entry.title
            link = entry.link
            summary = entry.get("summary", "")
            media_url = None

            if title in sent_titles:
                continue

            # Поиск изображения
            if "media_content" in entry:
                media_url = entry.media_content[0].get("url")
            elif "links" in entry:
                for link_obj in entry.links:
                    if link_obj.type.startswith("image"):
                        media_url = link_obj.href
                        break

            # Получение краткого текста
            brief = await summarize_article(summary)
            if not brief:
                continue

            # Хэштеги
            hashtags = []
            if "trump" in title.lower():
                hashtags.append("#Trump")
            if "ai" in title.lower() or "artificial intelligence" in summary.lower():
                hashtags.append("#AI")
            if "russia" in title.lower() or "ukraine" in title.lower():
                hashtags.append("#World")
            if "justice" in title.lower():
                hashtags.append("#Justice")

            caption = f"<b>{title}</b>\n\n{brief}\n\n<i>{feed.feed.title}</i>\n{' '.join(hashtags)}"

            try:
                if media_url:
                    photo = URLInputFile(media_url)
                    await bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=caption)
                else:
                    await bot.send_message(chat_id=CHANNEL_ID, text=caption)
                sent_titles.append(title)
                save_titles()
                posted += 1
                await asyncio.sleep(2)
            except Exception as e:
                logging.warning(f"Failed to send message: {e}")

# Цикл
async def scheduler():
    while True:
        await fetch_and_post()
        await asyncio.sleep(60)

# Запуск
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(scheduler())
