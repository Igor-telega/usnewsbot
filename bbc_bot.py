import os
import asyncio
import requests
from bs4 import BeautifulSoup
from newspaper import Article
from datetime import datetime, timezone
from aiogram import Bot
from dotenv import load_dotenv
from openai import OpenAI
from dateutil import parser as date_parser

load_dotenv()

TELEGRAM_TOKEN = os.getenv("BBC_TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=TELEGRAM_TOKEN)
client = OpenAI(api_key=OPENAI_API_KEY)

BBC_URL = "https://www.bbc.com/news"
POSTED_URLS_FILE = "bbc_posted_urls.txt"

def load_posted_urls():
    if os.path.exists(POSTED_URLS_FILE):
        with open(POSTED_URLS_FILE, "r") as f:
            return set(line.strip() for line in f)
    return set()

def save_posted_url(url):
    with open(POSTED_URLS_FILE, "a") as f:
        f.write(url + "\n")

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

def is_recent(article):
    try:
        if article.publish_date:
            now = datetime.now(timezone.utc)
            delta = now - article.publish_date
            return delta.total_seconds() < 3600
    except Exception:
        return False
    return False

async def get_articles():
    response = requests.get(BBC_URL)
    soup = BeautifulSoup(response.content, "html.parser")
    links = soup.find_all("a", href=True)

    seen = set()
    posted_urls = load_posted_urls()
    count = 0

    for link in links:
        href = link['href']
        if not href.startswith("/news/"):
            continue

        full_url = f"https://www.bbc.com{href}"
        if full_url in seen or full_url in posted_urls:
            continue
        seen.add(full_url)

        try:
            article = Article(full_url)
            article.download()
            article.parse()

            if len(article.text) < 300 or not is_recent(article):
                print(f"Пропущено (не актуально или короткое): {article.title}")
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
            save_posted_url(full_url)
            await asyncio.sleep(5)

            count += 1
            if count >= 2:
                break

        except Exception as e:
            print("Parsing error:", e)
            continue

async def main():
    await get_articles()

if __name__ == "__main__":
    asyncio.run(main())
