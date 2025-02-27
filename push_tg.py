#! /usr/bin/env python3

import os
import sqlite3
import telegram
import requests
import asyncio
import openai
from dotenv import load_dotenv
from datetime import datetime, timezone

from utils import log

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = "@topmathjournals"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

DB_FILE = "math_journals.db"

bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
client = openai.OpenAI(api_key=OPENAI_API_KEY)

def fetch_unpushed_articles():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("SELECT id, journal, title, link, summary, image_url, published_time FROM articles WHERE pushed_time = '' OR pushed_time IS NULL")
    articles = cursor.fetchall()

    conn.close()
    return articles

def download_image(image_url):
    # download image from image_url and save to ./images/
    # an example of image_url is: http://media.springernature.com/lw685/springer-static/image/art%3A10.1007%2Fs00222-024-01303-y/MediaObjects/222_2024_1303_Fig1_HTML.png
    if image_url.startswith("http://"):
        image_url = image_url.replace("http://", "https://")
    title = image_url.split("/")[-1]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        # "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        # "Accept-Encoding": "gzip, deflate, br, zstd",
    }
    for _ in range(1):
        try:
            response = requests.get(image_url, headers=headers)
            if response.status_code == 200:
                with open(f"./images/{title}", "wb") as f:
                    f.write(response.content)
                return f"./images/{title}"
            else:
                log("download image failed, status code: %s"%response.status_code,l=2)
                print(response.content)
        except Exception as e:
            log("failed to download image from %s"%image_url,l=3)
    return None

def translate_title(title):
    response = client.chat.completions.create(
        model="o1",
        messages=[{"role": "system", "content": "Please translate the following title of a mathematical academic paper into Chinese, ensuring accuracy and clarity. Do not include quotation marks in the response."},
                  {"role": "user", "content": title}]
    )
    return response.choices[0].message.content

async def send_to_telegram(article):
    article_id, journal, title, link, summary, image_url, published_time = article

    try:
        title_cn = translate_title(title)
    except Exception as e:
        log("failed to translate title: %s"%e,l=3)
        title_cn = None

    summary = summary.replace("\n", " ").replace("### Abstract", "").replace("\\(", "").replace("\\)", "").strip()

    message = f"_{journal}_\n"
    message += f"[{title}]({link})\n"
    if title_cn:
        message += f"{title_cn}\n"
    message += f"\n{summary}"

    # if image_url:
    #     try:
    #         image_url = image_url.replace("http://", "https://")
    #         await bot.send_photo(chat_id=TELEGRAM_CHAT_ID, photo=image_url, caption=message, parse_mode="Markdown")
    #     except Exception as e:
    #         log("failed to send photo to telegram: %s"%e,l=2)
    #         await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode="Markdown")
    # else:
    #     await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode="Markdown")

    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode="Markdown")

    return article_id

def update_pushed_time(article_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("UPDATE articles SET pushed_time = ? WHERE id = ?", (now, article_id))

    conn.commit()
    conn.close()

async def main():
    articles = fetch_unpushed_articles()

    if not articles:
        log("no new articles to push")
        return

    for article in articles:
        log("pushing %s"%article[2])
        article_id = await send_to_telegram(article)
        update_pushed_time(article_id)
        log("pushed %s to telegram"%article[2])

if __name__ == "__main__":
    asyncio.run(main())
    # image_url = "http://media.springernature.com/lw685/springer-static/image/art%3A10.1007%2Fs00222-024-01303-y/MediaObjects/222_2024_1303_Fig1_HTML.png"
    # image_path = download_image(image_url)
    # print(image_path)

    # title = "Iterations of symplectomorphisms and $p$ -adic analytic actions on the Fukaya category"
    # print(translate_title(title))
