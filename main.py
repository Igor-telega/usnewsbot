import os
import asyncio
import requests
from bs4 import BeautifulSoup
from newspaper import Article
from datetime import datetime
from aiogram import Bot
from dotenv import load_dotenv
from openai import OpenAI

# Загрузка переменных
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=TELEGRAM_TOKEN)
client = OpenAI(api_key=OPENAI_API_KEY)

CNN_URL = "https://edition.cnn.com/"
POSTED_FILE = "posted_urls.txt"

# Загружаем уже опубликованные ссылки
def load_posted_urls():
    if not os.path.exists(POSTED_FILE):
        return set()
    with open(POSTED_FILE, "r") as file:
        return set(line.strip() for line in file)

# Сохраняем новую ссылку
def save_posted_url(url):
    with open(POSTED_FILE, "a") as file:
        file.write(url + "\n")

async def summarize_article(text):
    prompt = (
        "Summarize the following article in the style of a professional journalist. "
        "Write in English for a U.S. audience in 6–10 sentences. Avoid saying 'the article says' or similar phrases. Just state the facts:\n\n"
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
        print("OpenAI Error:", e)
        return None

async def get_articles():
    posted_urls = load_posted_urls()
    response = requests.get(CNN_URL)
    soup = BeautifulSoup(response.content, "html.parser")
    links = soup.find_all("a", href=True)

    seen = set()
    count = 0

    for link in links:
        href = link['href']
        if not href.startswith("/"):
            continue
        if not "/202" in href:
            continue

        full_url = f"https://edition.cnn.com{href}"
        if full_url in seen or full_url in posted_urls:
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

            date_str = datetime.now().strftime("%Y-%m-%d %H:%M")

            message = (
                f"📰 <b>{article.title}</b>\n\n"
                f"{summary}\n\n"
                f"<i>Source: CNN</i>\n{date_str} #News #CNN"
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
