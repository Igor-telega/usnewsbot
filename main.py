import asyncio
import logging
import os
import requests
from aiogram import Bot
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import json

API_TOKEN = '8140535664:AAFwJahQG39PPha005tG-7fhAkjcYynCAaY'
CHANNEL_ID = '@usnewsdailytestchannel'
NEWSAPI_KEY = '2b681d33133d4b59b1342481d5a27432'  # ← твой актуальный ключ
POSTED_URLS_FILE = 'sent_titles.json'
LOG_FILE = 'log.txt'

bot = Bot(token=API_TOKEN)
posted_urls = set()

def load_posted_urls():
    if os.path.exists(POSTED_URLS_FILE):
        with open(POSTED_URLS_FILE, 'r') as f:
            return set(json.load(f))
    return set()

def save_posted_urls(posted_urls):
    with open(POSTED_URLS_FILE, 'w') as f:
        json.dump(list(posted_urls), f)

def log_publication(title, url):
    time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(LOG_FILE, 'a') as f:
        f.write(f'[{time}] Published: {title} | {url}\n')

def get_news():
    url = (
        "https://newsapi.org/v2/top-headlines?"
        "language=en&"
        "pageSize=10&"
        f"apiKey={NEWSAPI_KEY}"
    )
    response = requests.get(url)
    data = response.json()
    print("===== ОТВЕТ ОТ NEWSAPI =====")
    print(data)
    return data.get("articles", [])

def create_title_image(text, output_path="headline.png"):
    width, height = 1024, 512
    background = (0, 0, 0)
    text_color = (255, 255, 255)

    image = Image.new('RGB', (width, height), background)
    draw = ImageDraw.Draw(image)

    try:
        font = ImageFont.truetype("arial.ttf", 44)
    except:
        font = ImageFont.load_default()

    words = text.split()
    lines = []
    line = ''
    for word in words:
        test_line = line + word + ' '
        if draw.textlength(test_line, font=font) < width - 80:
            line = test_line
        else:
            lines.append(line)
            line = word + ' '
    lines.append(line)

    y = height // 2 - (len(lines) * 30)
    for line in lines:
        draw.text((50, y), line.strip(), fill=text_color, font=font)
        y += 50

    image.save(output_path)
    return output_path

async def send_article(article):
    try:
        url = article['url']
        title = article['title']
        description = article.get('description', '')

        print(f"\nПроверяю: {title}")

        if url in posted_urls:
            print("Уже публиковалась, пропускаем.")
            return

        print(f"Публикую: {title}")
        posted_urls.add(url)
        save_posted_urls(posted_urls)

        image_url = article.get('urlToImage')
        text = f"<b>{title}</b>\n\n{description.strip()}" if description else f"<b>{title}</b>"

        if image_url:
            await bot.send_photo(chat_id=CHANNEL_ID, photo=image_url, caption=text, parse_mode='HTML')
        else:
            print("Картинка не найдена — создаём обложку...")
            image_path = create_title_image(title)
            with open(image_path, 'rb') as photo:
                await bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=text, parse_mode='HTML')

        log_publication(title, url)
        print("Новость отправлена!")

    except Exception as e:
        logging.exception(f"Ошибка при публикации статьи: {e}")

async def news_loop():
    global posted_urls
    posted_urls = load_posted_urls()
    print("Бот запущен...")
    while True:
        articles = get_news()
        print(f"Получено {len(articles)} новостей")
        for article in articles:
            await send_article(article)
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(news_loop())
