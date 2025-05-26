import os
import json
import logging
import asyncio
import feedparser
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from openai import OpenAI

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Загрузка переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

NEWS_FEED_URL = "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"
SENT_TITLES_FILE = "sent_titles.json"

def load_sent_titles():
    try:
        with open(SENT_TITLES_FILE, "r") as file:
            data = json.load(file)
            return set(data.get("titles", []))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()

def save_sent_titles(titles):
    with open(SENT_TITLES_FILE, "w") as file:
        json.dump({"titles": list(titles)}, file)

async def summarize(title, content):
    prompt = (
        f"Write a short but complete news article (about 3-4 sentences) based on the headline and content below:\n\n"
        f"Headline: {title}\nContent: {content}\n\nArticle:"
    )

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=300,
        temperature=0.7
    )

    return response.choices[0].message.content.strip()

async def check_news():
    sent_titles = load_sent_titles()
    feed = feedparser.parse(NEWS_FEED_URL)
    new_titles = set()

    for entry in feed.entries[:10]:
        title = entry.title.strip()
        if title in sent_titles:
            continue

        content = entry.summary if hasattr(entry, "summary") else entry.get("description", "")
        try:
            summary = await summarize(title, content)
            text = f"<b>{title}</b>\n\n{summary}"
            await bot.send_message(chat_id=CHANNEL_ID, text=text)
            logging.info(f"Sent: {title}")
            new_titles.add(title)
        except Exception as e:
            logging.error(f"Error sending news: {e}")

    if new_titles:
        sent_titles.update(new_titles)
        save_sent_titles(sent_titles)

async def main():
    while True:
        await check_news()
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
