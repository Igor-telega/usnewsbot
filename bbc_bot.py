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
SEEN_TITLES_FILE = "seen_titles.json"


def load_seen_titles():
    if os.path.exists(SEEN_TITLES_FILE):
        with open(SEEN_TITLES_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_seen_titles(seen_titles):
    with open(SEEN_TITLES_FILE, "w") as f:
        json.dump(list(seen_titles), f)


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
    seen_titles = load_seen_titles()
    response = requests.get(BBC_URL)
    soup = BeautifulSoup(response.content, "html.parser")
    links = soup.find_all("a", href=True)

    count = 0

    for link in links:
        href = link['href']
        if not href.startswith("/news/"):
            continue

        full_url = f"https://www.bbc.com{href}"

        try:
            article = Article(full_url)
            article.download()
            article.parse()

            title = article.title.strip()
            if title in seen_titles:
                print(f"Пропущено (заголовок уже был): {title}")
                continue

            summary = await summarize_article(article.text)
            if not summary:
                continue

            message = (
                f"📰 <b>{title}</b>\n\n"
                f"{summary}\n\n"
                f"<i>Source: BBC</i>"
            )

            await bot.send_message(chat_id=CHANNEL_ID, text=message, parse_mode="HTML")
            seen_titles.add(title)
            save_seen_titles(seen_titles)

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
