mport os
import logging
import json
import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.types import InputMediaPhoto
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from newspaper import Article
import openai
import feedparser

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()
openai.api_key = OPENAI_API_KEY

NEWS_FEEDS = {
    "NY Times": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "CNN": "http://rss.cnn.com/rss/cnn_topstories.rss",
    "Reuters": "http://feeds.reuters.com/reuters/topNews",
    "AP": "https://rss.apnews.com/rss/apf-topnews",
    "NPR": "https://www.npr.org/rss/rss.php?id=1001",
    "The Guardian": "https://www.theguardian.com/world/rss"
}

SENT_TITLES_FILE = "sent_titles.json"


def load_sent_titles():
    if not os.path.exists(SENT_TITLES_FILE):
        return set()
    with open(SENT_TITLES_FILE, "r") as f:
        data = json.load(f)
        return set(data.get("titles", []))


def save_sent_titles(titles):
    with open(SENT_TITLES_FILE, "w") as f:
        json.dump({"titles": list(titles)}, f)


def extract_keywords(text):
    text = text.lower()
    keywords = []
    if "trump" in text:
        keywords.append("#Trump")
    if any(word in text for word in ["ukraine", "russia", "israel", "gaza", "war", "strike"]):
        keywords.append("#World")
    if any(word in text for word in ["ai", "artificial intelligence", "technology"]):
        keywords.append("#AI")
    if any(word in text for word in ["court", "trial", "judge", "charged"]):
        keywords.append("#Justice")
    return " ".join(keywords)


async def summarize_article(url):
    try:
        article = Article(url)
        article.download()
        article.parse()
        prompt = f"Summarize this news article in 2-4 sentences as a news brief for Telegram:

Title: {article.title}

Text: {article.text}"
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        summary = response.choices[0].message.content.strip()
        return summary
    except Exception as e:
        logging.warning(f"Error summarizing article: {e}")
        return None


async def send_news():
    sent_titles = load_sent_titles()
    new_posts = []

    for source, url in NEWS_FEEDS.items():
        feed = feedparser.parse(url)
        for entry in feed.entries:
            if entry.title in sent_titles:
                continue
            summary = await summarize_article(entry.link)
            if not summary:
                continue
            image_url = entry.get("media_content", [{}])[0].get("url") if "media_content" in entry else None
            keywords = extract_keywords(entry.title + summary)

            caption = f"<b>{entry.title}</b>

{summary}

<i>{source}</i>
{keywords}"
            new_posts.append((caption, image_url))
            sent_titles.add(entry.title)
            if len(new_posts) >= 5:
                break
        if len(new_posts) >= 5:
            break

    for caption, image_url in new_posts:
        try:
            if image_url:
                await bot.send_photo(CHANNEL_ID, photo=image_url, caption=caption)
            else:
                await bot.send_message(CHANNEL_ID, caption)
        except Exception as e:
            logging.warning(f"Failed to send news: {e}")

    save_sent_titles(sent_titles)


async def main():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_news, "interval", minutes=1)
    scheduler.start()
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
