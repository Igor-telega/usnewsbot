import os
import asyncio
import logging
from datetime import datetime, timedelta
import feedparser
import openai
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from tiktoken import encoding_for_model
from embeddings import get_embedding, is_duplicate, save_embedding
from image_gen import generate_image

# Логирование
logging.basicConfig(level=logging.INFO)

# Переменные окружения
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")  # строка, например, "-1001234567890"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# Источники новостей
RSS_FEEDS = [
    ("https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml", "NYT"),
    ("http://feeds.bbci.co.uk/news/rss.xml", "BBC"),
    ("http://rss.cnn.com/rss/edition.rss", "CNN")
]

# Загрузка отправленных заголовков
import json
sent_titles_path = "sent_titles.json"
if os.path.exists(sent_titles_path):
    with open(sent_titles_path, "r") as f:
        sent_titles = json.load(f)
else:
    sent_titles = []

# Сохранить отправленные заголовки
def save_sent_titles():
    with open(sent_titles_path, "w") as f:
        json.dump(sent_titles, f)

# Сжать текст
def summarize(text):
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Ты журналист. Суммируй новость в 7–10 предложениях для американской англоязычной аудитории. Без заголовка, без ссылок. Укажи источник и дату. Тон нейтральный, информативный."},
            {"role": "user", "content": text}
        ]
    )
    return response.choices[0].message.content.strip()

# Получить посты
async def get_news_posts():
    posts_by_source = {}
    since = datetime.utcnow() - timedelta(days=1)
    for url, source in RSS_FEEDS:
        feed = feedparser.parse(url)
        source_posts = []
        for entry in feed.entries:
            if hasattr(entry, "published_parsed"):
                published = datetime(*entry.published_parsed[:6])
                if published < since:
                    continue
            title = entry.title
            if title in sent_titles:
                continue
            summary = entry.summary if hasattr(entry, "summary") else entry.get("description", "")
            content = f"{title}

{summary}"
            emb = get_embedding(content)
            if is_duplicate(emb, [get_embedding(t) for t in sent_titles]):
                continue
            text = summarize(content)
            img = generate_image(title)
            source_posts.append((title, text, img, source, published.strftime("%b %d, %Y")))
        posts_by_source[source] = source_posts
    return posts_by_source

# Распределить посты по источникам
def interleave_posts(posts_by_source):
    result = []
    source_lists = list(posts_by_source.values())
    max_len = max(len(lst) for lst in source_lists)
    for i in range(max_len):
        for lst in source_lists:
            if i < len(lst):
                result.append(lst[i])
    return result

# Основной цикл
async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    @dp.startup()
    async def on_startup(dispatcher):
        logging.info("Bot started")
        posts_by_source = await get_news_posts()
        posts = interleave_posts(posts_by_source)

        for title, text, image_url, source, date_str in posts[:5]:
            try:
                message = f"{text}

Source: {source}
Published: {date_str}"
                await bot.send_photo(chat_id=CHANNEL_ID, photo=image_url, caption=message)
                sent_titles.append(title)
                save_embedding(title, get_embedding(title))
            except Exception as e:
                logging.error(f"Failed to send post: {e}")
        save_sent_titles()

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
