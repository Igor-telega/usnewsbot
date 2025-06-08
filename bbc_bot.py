import os
import json
import asyncio
import requests
from bs4 import BeautifulSoup
from newspaper import Article
from aiogram import Bot
from dotenv import load_dotenv
from openai import OpenAI

# Загрузка переменных
load_dotenv()
TELEGRAM_TOKEN = os.getenv("BBC_TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=TELEGRAM_TOKEN)
client = OpenAI(api_key=OPENAI_API_KEY)

BBC_URL = "https://www.bbc.com/news"

# Файлы для хранения истории
TITLE_STORAGE_FILE = "bbc_sent_titles.json"
SUMMARY_STORAGE_FILE = "bbc_sent_summaries.json"

def load_json(file):
    try:
        with open(file, "r") as f:
            return json.load(f)
    except Exception:
        return []

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f)

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
    sent_titles = load_json(TITLE_STORAGE_FILE)
    sent_summaries = load_json(SUMMARY_STORAGE_FILE)

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
        if full_url in seen:
            continue
        seen.add(full_url)

        try:
            article = Article(full_url)
            article.download()
            article.parse()

            if article.title in sent_titles:
                print("Пропущено (заголовок уже был):", article.title)
                continue

            summary = await summarize_article(article.text)
            if not summary:
                continue

            if summary in sent_summaries:
                print("Пропущено (summary уже был):", article.title)
                continue

            message = (
                f"📰 <b>{article.title}</b>\n\n"
                f"{summary}\n\n"
                f"<i>Source: BBC</i>"
            )

            await bot.send_message(chat_id=CHANNEL_ID, text=message, parse_mode="HTML")
            await asyncio.sleep(5)

            sent_titles.append(article.title)
            sent_summaries.append(summary)
            save_json(TITLE_STORAGE_FILE, sent_titles)
            save_json(SUMMARY_STORAGE_FILE, sent_summaries)

            count += 1
            if count >= 2:
                break

        except Exception as e:
            print("Ошибка парсинга:", e)
            continue

async def main():
    await get_articles()

if __name__ == "__main__":
    asyncio.run(main())
