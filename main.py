import asyncio
import os
import feedparser
import requests
import hashlib
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.types import InputFile
from openai import OpenAI
from dotenv import load_dotenv
import json

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai = OpenAI(api_key=OPENAI_API_KEY)

RSS_FEEDS = {
    "NYT": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "CNN": "http://rss.cnn.com/rss/cnn_topstories.rss",
    "Reuters": "http://feeds.reuters.com/reuters/topNews",
    "AP": "https://apnews.com/rss",
    "The Guardian": "https://www.theguardian.com/world/rss"
}

MAX_POSTS_PER_RUN = 5
SENT_TITLES_FILE = "sent_titles.json"

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

def load_sent_hashes():
    if not os.path.exists(SENT_TITLES_FILE):
        return []
    with open(SENT_TITLES_FILE, "r") as file:
        data = json.load(file)
        return data.get("hashes", [])

def save_sent_hashes(hashes):
    with open(SENT_TITLES_FILE, "w") as file:
        json.dump({"hashes": hashes}, file)

def generate_hash(title, summary):
    return hashlib.sha256((title + summary).encode("utf-8")).hexdigest()

async def summarize_text(text):
    chat_completion = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": (
                "You are a professional news editor for a U.S. audience. "
                "Summarize this news in 4–6 sentences in a clear, journalistic tone. "
                "Avoid phrases like 'this article states'. Focus on facts, avoid repeating the title."
            )},
            {"role": "user", "content": text}
        ]
    )
    return chat_completion.choices[0].message.content.strip()

async def generate_image(prompt, filename="news_image.jpg"):
    try:
        response = openai.images.generate(prompt=prompt, model="dall-e-3", n=1, size="1024x1024")
        image_url = response.data[0].url
        image_data = requests.get(image_url).content
        with open(filename, "wb") as f:
            f.write(image_data)
        return filename
    except Exception as e:
        print(f"Image generation error: {e}")
        return None

def classify_hashtags(title, summary):
    text = (title + " " + summary).lower()
    tags = []
    if any(w in text for w in ["biden", "trump", "senate", "white house", "republican", "democrat"]):
        tags.append("#Politics")
    if any(w in text for w in ["war", "ukraine", "russia", "nato", "gaza", "israel", "iran"]):
        tags.append("#Conflict")
    if any(w in text for w in ["ai", "technology", "chatgpt", "robot", "tech"]):
        tags.append("#Tech")
    if any(w in text for w in ["inflation", "market", "jobs", "economy", "budget"]):
        tags.append("#Economy")
    if any(w in text for w in ["crime", "shooting", "police", "arrest"]):
        tags.append("#Crime")
    if not tags:
        tags.append("#News")
    return " ".join(tags[:3])

async def fetch_and_send_news():
    sent_hashes = load_sent_hashes()
    new_hashes = []

    for source, url in RSS_FEEDS.items():
        feed = feedparser.parse(url)
        count = 0
        for entry in feed.entries:
            summary = getattr(entry, 'summary', '') or getattr(entry, 'description', '')
            news_hash = generate_hash(entry.title, summary)
            if news_hash in sent_hashes or news_hash in new_hashes:
                continue

            try:
                summarized = await summarize_text(f"{entry.title}\n\n{summary}")
            except Exception as e:
                print("OpenAI summarization error:", e)
                continue

            hashtags = classify_hashtags(entry.title, summary)
            message = f"<b>{entry.title}</b>\n\n{summarized}\n\n<i>{source}</i>\n{hashtags}"

            try:
                image_url = None
                if "media_content" in entry and entry.media_content:
                    image_url = entry.media_content[0].get("url")

                if image_url:
                    image_data = requests.get(image_url).content
                    with open("temp.jpg", "wb") as f:
                        f.write(image_data)
                    photo = InputFile("temp.jpg")
                    await bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=message)
                    os.remove("temp.jpg")
                else:
                    image_path = await generate_image(entry.title)
                    if image_path:
                        await bot.send_photo(chat_id=CHANNEL_ID, photo=InputFile(image_path), caption=message)
                        os.remove(image_path)
                    else:
                        await bot.send_message(chat_id=CHANNEL_ID, text=message)
            except Exception as e:
                print(f"Error sending message: {e}")

            new_hashes.append(news_hash)
            count += 1
            if count >= MAX_POSTS_PER_RUN:
                break

    save_sent_hashes(sent_hashes + new_hashes)

async def main():
    while True:
        try:
            await fetch_and_send_news()
        except Exception as e:
            print(f"Error during fetch: {e}")
        await asyncio.sleep(300)  # каждые 5 минут

if __name__ == "__main__":
    asyncio.run(main())
