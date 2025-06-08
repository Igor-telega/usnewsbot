import os
import asyncio
from aiogram import Bot, Dispatcher
from newspaper import Article
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

CNN_URL = "https://edition.cnn.com/"

async def get_latest_articles():
    response = requests.get(CNN_URL)
    soup = BeautifulSoup(response.content, "html.parser")
    links = soup.find_all("a", href=True)

    sent = 0
    for link in links:
        href = link['href']
        if href.startswith("/"):
            full_url = f"https://edition.cnn.com{href}"
        elif href.startswith("https://"):
            full_url = href
        else:
            continue

        # Пропустим повторяющиеся/ненужные
        if "/videos/" in full_url or "/live-news/" in full_url:
            continue

        try:
            article = Article(full_url)
            article.download()
            article.parse()

            title = article.title
            text = article.text[:1000]  # Ограничим объём
            date = datetime.now().strftime("%Y-%m-%d %H:%M")

            message = f"📰 <b>{title}</b>\n\n{text}\n\n<a href='{full_url}'>Источник (CNN)</a>\n{date} #News #CNN"

            await bot.send_message(chat_id=CHANNEL_ID, text=message, parse_mode="HTML", disable_web_page_preview=False)
            sent += 1
            await asyncio.sleep(5)

            if sent >= 2:
                break

        except Exception as e:
            print("Ошибка:", e)
            continue

async def main():
    await get_latest_articles()

if __name__ == "__main__":
    asyncio.run(main())
