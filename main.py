from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from dotenv import load_dotenv
import os

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

bot = Bot(token=TELEGRAM_TOKEN)  # убрали parse_mode отсюда
dp = Dispatcher(bot)

@dp.message_handler(commands=["start"])
async def start_handler(message: types.Message):
    await message.answer("News bot is running!")

async def send_news_to_channel(text, image_url=None):
    if image_url:
        await bot.send_photo(chat_id=CHANNEL_ID, photo=image_url, caption=text, parse_mode="HTML")
    else:
        await bot.send_message(chat_id=CHANNEL_ID, text=text, parse_mode="HTML")

# Пример вызова
# await send_news_to_channel("Your <b>news</b> message", "https://example.com/image.jpg")

# Запуск
if __name__ == "__main__":
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True)
