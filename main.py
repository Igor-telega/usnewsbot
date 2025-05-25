import os
import json
import requests
import feedparser
from PIL import Image
from io import BytesIO
from telegram import Bot
from openai import OpenAI

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

openai = OpenAI(api_key=OPENAI_API_KEY)

def summarize_article(title, description):
    prompt = f"Summarize the following news story in one clear sentence:\nTitle: {title}\nDescription: {description}"
    response = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()

def load_sent_titles():
    if not os.path.exists("sent_titles.json"):
        return []
    with open("sent_titles.json", "r") as f:
        return json.load(f).get("titles", [])

def save_sent_titles(titles):
    with open("sent_titles.json", "w") as f:
        json.dump({"titles": titles}, f)

def send_news():
    bot = Bot(token=BOT_TOKEN)
    sent_titles = load_sent_titles()

    feeds = [
        "http://feeds.reuters.com/reuters/topNews",
        "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
        "https://feeds.a.dj.com/rss/RSSWorldNews.xml",
        "http://rss.cnn.com/rss/cnn_topstories.rss",
        "https://www.npr.org/rss/rss.php?id=1001"
    ]

    for feed_url in feeds:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            title = entry.title
            summary = entry.summary if hasattr(entry, "summary") else ""
            image_url = entry.media_content[0]["url"] if "media_content" in entry else None

            if title not in sent_titles:
                summary_text = summarize_article(title, summary)
                caption = f"<b>{title}</b>\n\n{summary_text}"

                if image_url:
                    image_response = requests.get(image_url)
                    if image_response.status_code == 200:
                        bot.send_photo(chat_id=CHANNEL_ID, photo=BytesIO(image_response.content), caption=caption, parse_mode="HTML")
                    else:
                        bot.send_message(chat_id=CHANNEL_ID, text=caption, parse_mode="HTML")
                else:
                    bot.send_message(chat_id=CHANNEL_ID, text=caption, parse_mode="HTML")

                sent_titles.append(title)

    save_sent_titles(sent_titles)

if __name__ == "__main__":
    send_news()
