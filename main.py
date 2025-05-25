import os
import json
import requests
import asyncio
import feedparser
from io import BytesIO
from telegram import Bot
from openai import AsyncOpenAI
from PIL import Image

bot = Bot(token=os.getenv("BOT_TOKEN"))
channel_id = os.getenv("CHANNEL_ID")
openai_api_key = os.getenv("OPENAI_API_KEY")
client = AsyncOpenAI(api_key=openai_api_key)

news_feeds = [
    "http://feeds.reuters.com/reuters/topNews",
    "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "https://feeds.a.dj.com/rss/RSSWorldNews.xml",
    "https://www.npr.org/rss/rss.php?id=1001",
    "https://www.politico.com/rss/politics08.xml",
]

async def summarize(title, description):
    prompt = f"Summarize the following news story in one clear sentence:\nTitle: {title}\nDescription: {description}"
    response = await client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=60
    )
    return response.choices[0].message.content.strip()

def get_image_url(entry):
    if "media_content" in entry:
        return entry.media_content[0]["url"]
    if "links" in entry:
        for link in entry.links:
            if link.get("type", "").startswith("image"):
                return link["href"]
    return None

async def send_news():
    with open("sent_titles.json", "r") as f:
        sent_data = json.load(f)
    sent_titles = sent_data.get("titles", [])

    for url in news_feeds:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            title = entry.title
            if title in sent_titles:
                continue
            description = entry.summary if "summary" in entry else ""
            summary_text = await summarize(title, description)

            image_url = get_image_url(entry)
            if image_url:
                try:
                    response = requests.get(image_url)
                    image = BytesIO(response.content)
                    await bot.send_photo(chat_id=channel_id, photo=image, caption=f"{title}\n\n{summary_text}")
                except:
                    await bot.send_message(chat_id=channel_id, text=f"{title}\n\n{summary_text}")
            else:
                await bot.send_message(chat_id=channel_id, text=f"{title}\n\n{summary_text}")

            sent_titles.append(title)
            with open("sent_titles.json", "w") as f:
                json.dump({"titles": sent_titles[-100:]}, f, indent=2)
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(send_news())
