import os
import asyncio
import requests
import psycopg2
from bs4 import BeautifulSoup
from newspaper import Article
from datetime import datetime
from aiogram import Bot
from dotenv import load_dotenv
from openai import OpenAI

# Загрузка переменных окружения
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

DB_HOST = "dpg-d12top95pdvs73d4vhlg-a"
DB_NAME = "usnewsbot_db"
DB_USER = "usnewsbot_db_user"
DB_PASS = "tx3xULeRfo8XEovEz3iXDvgCSLaFDq0s"
DB_PORT = "5432"

bot = Bot(token=TELEGRAM_TOKEN)
client = OpenAI(api_key=OPENAI_API_KEY)

CNN_URL = "https://edition.cnn.com/"

# Подключение к БД
def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        port=DB_PORT
    )

# Создание таблицы, если ещё нет
def create_table():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS posted_articles (
            url TEXT PRIMARY KEY
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

# Проверка, была ли статья уже опубликована
def is_posted(url):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM posted_articles WHERE url = %s;", (url,))
    result = cur.fetchone()
    cur.close()
    conn.close()
    return result is not None

# Сохраняем ссылку на опубликованную статью
def save_posted(url):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO posted_articles (url) VALUES (%s);", (url,))
    conn.commit()
    cur.close()
    conn.close()

# Резюме статьи
async def summarize_article(text):
    prompt = (
        "Make a concise news summary in journalistic style for American readers, in 6–10 sentences. No introduction phrases like 'The article says'. Just the facts:\n\n"
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

# Главная логика
async def get_articles():
    response = requests.get(CNN_URL)
    soup = BeautifulSoup(response.content, "html.parser")
    links = soup.find_all("a", href=True)

    seen = set()
    count = 0

    for link in links:
        href = link['href']
        if not href.startswith("/"):
            continue
        if "/202" not in href:
            continue

        full_url = f"https://edition.cnn.com{href}"
        if full_url in seen or is_posted(full_url):
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
            save_posted(full_url)
            await asyncio.sleep(5)

            count += 1
            if count >= 2:
                break

        except Exception as e:
            print("Parsing error:", e)
            continue

async def main():
    create_table()
    try:
        await get_articles()
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
