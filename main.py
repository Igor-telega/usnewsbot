import os
import asyncio
import requests
from bs4 import BeautifulSoup
from newspaper import Article
from datetime import datetime, timedelta
from aiogram import Bot
from dotenv import load_dotenv
from openai import OpenAI

# Загрузка переменных окружения
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=TELEGRAM_TOKEN)
client = OpenAI(api_key=OPENAI_API_KEY)

CNN_URL = "https://edition.cnn.com/"

async def summarize_article(text):
    prompt = (
        "Сделай краткое журналистское резюме этой статьи на английском языке для США. "
        "6–10 предложений. Без фраз вроде 'в статье говорится'. Просто факты:\n\n"
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
        print("Ошибка OpenAI:", e)
        return None

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
        if not "/202" in href:
            continue

        full_url = f"https://edition.cnn.com{href}"
        if full_url in seen:
            continue
        seen.add(full_url)

        try:
            article = Article(full_url)
            article.download()
            article.parse()

            # Проверка даты публикации: не старше 1 часа
            if article.publish_date:
                age = datetime.utcnow() - article.publish_date.replace(tzinfo=None)
                if age > timedelta(hours=1):
                    print(f"Пропущено (старое): {article.title}")
                    continue

            if len(article.text) < 300:
                continue

            summary = await summarize_article(article.text)
            if not summary:
                continue

            message = (
                f"📰 <b>{article.title}</b>\n\n"
                f"{summary}\n\n"
                f"<i>Источник: CNN</i> #News #CNN"
            )

            await bot.send_message(chat_id=CHANNEL_ID, text=message, parse_mode="HTML")
            await asyncio.sleep(5)

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
