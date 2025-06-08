import os
import asyncio
import requests
from bs4 import BeautifulSoup
from newspaper import Article
from datetime import datetime, timezone
from aiogram import Bot
from dotenv import load_dotenv
from openai import OpenAI
import hashlib
import json

load_dotenv()

TELEGRAM_TOKEN = os.getenv("BBC_TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=TELEGRAM_TOKEN)
client = OpenAI(api_key=OPENAI_API_KEY)

BBC_URL = "https://www.bbc.com/news"
URL_LOG_FILE = "bbc_posted_urls.txt"

def read_posted_urls():
    if not os.path.exists(URL_LOG_FILE):
        return set()
    with open(URL_LOG_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f)

def save_posted_url(url):
    with open(URL_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{url}\n")

async def summarize_article(text):
    prompt = (
        "Summarize the following BBC news article in 6–10 simple, factual sentences for a US audience. "
        "Do not say 'the article says'. Use plain news language:\n\n"
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
        print("OpenAI summarization error:", e)
        return None

def extract_publish_date(article_url):
    try:
        html = requests.get(article_url, timeout=10).text
        soup = BeautifulSoup(html, "html.parser")

        meta_time = soup.find("meta", {"property": "article:published_time"})
        if meta_time and meta_time.get("content"):
            return datetime.fromisoformat(meta_time["content"].replace("Z", "+00:00"))

        time_tag = soup.find("time")
        if time_tag and time_tag.get("datetime"):
            return datetime.fromisoformat(time_tag["datetime"].replace("Z", "+00:00"))

        scripts = soup.find_all("script", {"type": "application/ld+json"})
        for script in scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and "datePublished" in data:
                    return datetime.fromisoformat(data["datePublished"].replace("Z", "+00:00"))
            except:
                continue
    except Exception as e:
        print("Ошибка извлечения даты:", e)
    return None

def is_recent(pub_date):
    if not pub_date:
        return False
    now = datetime.now(timezone.utc)
    return (now - pub_date).total_seconds() < 3600

async def get_articles():
    posted_urls = read_posted_urls()
    response = requests.get(BBC_URL)
    soup = BeautifulSoup(response.content, "html.parser")
    links = soup.find_all("a", href=True)

    seen_urls = set()
    count = 0

    for link in links:
        href = link['href']

        # ⚠️ Пропускаем всё, что не похоже на статью
        if not (href.startswith("/news/articles/") or (href.startswith("/news/") and href[6:].split("/")[0].isdigit())):
            continue

        full_url = f"https://www.bbc.com{href}"
        if full_url in seen_urls or full_url in posted_urls:
            print(f"Пропущено (уже отправлено): {full_url}")
            continue
        seen_urls.add(full_url)

        try:
            article = Article(full_url)
            article.download()
            article.parse()

            pub_date = extract_publish_date(full_url)
            if not is_recent(pub_date):
                print(f"Пропущено (не актуально): {article.title}")
                continue

            if len(article.text.strip()) < 100:
                print(f"Пропущено (слишком короткое): {article.title}")
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
            print(f"✅ Отправлено: {article.title}")
            save_posted_url(full_url)
            count += 1
            if count >= 2:
                break

            await asyncio.sleep(5)

        except Exception as e:
            print("Ошибка при обработке статьи:", e)
            continue

async def main():
    await get_articles()

if __name__ == "__main__":
    asyncio.run(main())
