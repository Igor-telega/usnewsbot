import os
import asyncio
import requests
from bs4 import BeautifulSoup
from newspaper import Article
from datetime import datetime
from aiogram import Bot
from dotenv import load_dotenv
import openai
import hashlib

load_dotenv()

TELEGRAM_TOKEN = os.getenv("BBC_TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=TELEGRAM_TOKEN)
openai.api_key = OPENAI_API_KEY

BBC_URL = "https://www.bbc.com/news"
sent_titles = set()
sent_embeddings = []

SIMILARITY_THRESHOLD = 0.90

async def cosine_similarity(vec1, vec2):
    import numpy as np
    a = np.array(vec1)
    b = np.array(vec2)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

async def is_unique(text):
    try:
        response = openai.Embedding.create(
            model="text-embedding-3-small",
            input=text
        )
        new_embedding = response["data"][0]["embedding"]

        for old_embedding in sent_embeddings:
            similarity = await cosine_similarity(new_embedding, old_embedding)
            if similarity > SIMILARITY_THRESHOLD:
                return False

        sent_embeddings.append(new_embedding)
        return True
    except Exception as e:
        print("OpenAI Embedding error:", e)
        return True  # на всякий случай считаем уникальной, если ошибка

async def summarize_article(text):
    prompt = (
        "Summarize this BBC news article in 6–10 simple sentences for a US audience:\n\n"
        f"{text}"
    )
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=600
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("OpenAI Summary error:", e)
        return None

async def get_articles():
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

            if not article.title or article.title in sent_titles:
                print("Пропущено (заголовок уже был):", article.title)
                continue

            if not await is_unique(article.text):
                print("Пропущено (похоже на уже отправленное):", article.title)
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
            sent_titles.add(article.title)
            print("✅ Отправлено:", article.title)

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
