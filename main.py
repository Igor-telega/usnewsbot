import asyncio
import feedparser
import os
import json
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from openai import OpenAI
from image_gen import generate_image
from embeddings import get_embedding, is_duplicate, save_embedding
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot=bot)

sources = {
    "NYT": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "BBC": "https://feeds.bbci.co.uk/news/rss.xml",
    "CNN": "http://rss.cnn.com/rss/edition.rss"
}

sent_titles_file = "sent_titles.json"
if os.path.exists(sent_titles_file):
    with open(sent_titles_file, "r") as f:
        sent_titles = set(json.load(f))
else:
    sent_titles = set()

async def fetch_feed(source_name, url):
    feed = feedparser.parse(url)
    one_day_ago = datetime.utcnow() - timedelta(days=1)
    for entry in feed.entries:
        try:
            title = entry.title.strip()
            if title in sent_titles:
                continue

            # Check publication date
            published = entry.get("published_parsed") or entry.get("updated_parsed")
            if not published:
                continue
            pub_date = datetime(*published[:6])
            if pub_date < one_day_ago:
                continue

            content = entry.get("summary", "")
            image_url = ""
            if "media_content" in entry and entry.media_content:
                image_url = entry.media_content[0].get("url", "")

            embedding = get_embedding(title)
            if is_duplicate(embedding, [], threshold=0.91):
                continue

            # Prompt to summarize
            prompt = f"Summarize the following news article for a U.S. audience in professional journalistic style. Limit it to 8–10 sentences. Avoid promotional tone.\n\nTitle: {title}\n\nContent: {content}"
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a professional news editor writing for a major U.S. audience."},
                    {"role": "user", "content": prompt}
                ]
            )
            summary = response.choices[0].message.content.strip()

            hashtags = " ".join([f"#{word}" for word in title.split() if word.istitle() and len(word) > 2][:5])
            date = pub_date.strftime("%b %d, %Y")

            text = (
                f"<b>{title}</b>\n\n"
                f"{summary}\n\n"
                f"<i>Source:</i> {source_name}\n"
                f"<i>Published:</i> {date}\n"
                f"{hashtags}"
            )

            if not image_url:
                image_url = generate_image(title)

            await bot.send_photo(CHANNEL_ID, photo=image_url, caption=text, parse_mode="HTML")

            sent_titles.add(title)
            save_embedding(title, embedding)

        except Exception as e:
            print(f"Error processing entry: {e}")

async def main():
    while True:
        tasks = []
        for i, source in enumerate(sources):
            url = sources[source]
            tasks.append(fetch_feed(source, url))
        await asyncio.gather(*tasks)

        with open(sent_titles_file, "w") as f:
            json.dump(list(sent_titles), f)

        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
