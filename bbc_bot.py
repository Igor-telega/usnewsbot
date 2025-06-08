import os
import json
import asyncio
import requests
from bs4 import BeautifulSoup
from newspaper import Article
from datetime import datetime, timezone
from aiogram import Bot
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

TELEGRAM_TOKEN = os.getenv("BBC_TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=TELEGRAM_TOKEN)
client = OpenAI(api_key=OPENAI_API_KEY)

BBC_URL = "https://www.bbc.com/news"
PUBLISHED_FILE = "published_bbc.json"

# Загружаем уже опубликованные статьи
if os.path.exists(PUBLISHED_FILE):
    with open(PUBLISHED_FILE, "r") as f:
        published_urls = set(json.load(f))
else:
    published_urls = set()

async def summarize_article(text):
    prompt = (
        "Summarize the following news article in 6–10 simple, factual sentences for a US audience. "
        "Do not say 'the article says' or 'it is mentioned that'.\n\n"
        f"{text}"
    )
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=600
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("OpenAI error:", e)
        return None

async def get_articles():
    global published_urls
    response = requests.get(BBC_URL)
    soup = BeautifulSoup(response.content, "html.parser")
    links = soup.find_all("a", href=True)

    seen = set()
    count = 0

    for link in links:
        href = link['href']
        if not href.startswith("/news/"):
            continue

        full_url = f"https://www.bbc.com{href}"
        if full_url in seen or full_url in published_urls:
            continue
        seen.add(full_url)

        try:
            article = Article(full_url)
            article.download()
            article.parse()

            if len(article.text) < 300:
                continue

            summary = await summarize_article(article.text)
            if not summary:
                continue

            message = (
                f"📰 <b>{article.title}</b>\n\n"
                f"{summary}\n\n"
                f"<i>Source: BBC</i>"
            )

            await bot.send_message(chat_id=CHANNEL_ID, text=message, parse_mode="HTML")
            published_urls.add(full_url)

            # Сохраняем новые ссылки
            with open(PUBLISHED_FILE, "w") as f:
                json.dump(list(published_urls), f)

            await asyncio.sleep(5)

            count += 1
            if count >= 2:
                break

        except Exception as e:
            print("Parsing error:", e)
            continue

async def main():
    try:
        await get_articles()
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
