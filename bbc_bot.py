import os
import asyncio
import requests
from bs4 import BeautifulSoup
from newspaper import Article
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
POSTED_URLS_FILE = "bbc_posted_urls.txt"

def is_recent(article):
    # Пока что пропускаем все статьи. Добавим точную проверку позже.
    return True

def is_already_posted(url):
    if not os.path.exists(POSTED_URLS_FILE):
        return False
    with open(POSTED_URLS_FILE, "r") as f:
        return url.strip() in f.read()

def mark_as_posted(url):
    with open(POSTED_URLS_FILE, "a") as f:
        f.write(url.strip() + "\n")

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
    response = requests.get(BBC_URL)
    soup = BeautifulSoup(response.content, "html.parser")
    links = soup.find_all("a", href=True)

    seen = set()
    count = 0

    for link in links:
        href = link['href']
        if not href.startswith("/news/") or href.startswith("/news/live"):
            continue

        full_url = f"https://www.bbc.com{href}"
        if full_url in seen or is_already_posted(full_url):
            continue
        seen.add(full_url)

        try:
            article = Article(full_url)
            article.download()
            article.parse()

            if not is_recent(article):
                print(f"Пропущено (устаревшее): {article.title}")
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
            mark_as_posted(full_url)
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
