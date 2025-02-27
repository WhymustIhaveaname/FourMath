#! /usr/bin/env python3

import feedparser
import sqlite3
import time
import requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from markdownify import markdownify

from utils import log

RSS_FEEDS = {
    "Annals of Mathematics": "https://annals.math.princeton.edu/rss.xml",
    "JAMS": "https://www.ams.org/rss/jams.xml",
    "Inventiones Mathematicae": "https://link.springer.com/search.rss?facet-journal-id=222&channel-name=Inventiones+Mathematicae",
    "Acta Mathematica": "https://www.mittag-leffler.se/rss.xml"
}


DB_FILE = "math_journals.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            journal TEXT,
            title TEXT,
            link TEXT,
            summary TEXT,
            image_url TEXT,
            published_time TEXT,
            pushed_time TEXT
        )
    ''')
    conn.commit()
    conn.close()

def extract_image(article_url):
    try:
        response = requests.get(article_url, timeout=5)
        soup = BeautifulSoup(response.text, "html.parser")
        images = soup.find_all("img")

        for img in images:
            width = int(img.get("width", 0))
            height = int(img.get("height", 0))
            if width < 300 or height < 200:
                continue

            img_url = img.get("src")
            if not img_url:
                continue

            # exclude base64 image
            if img_url.startswith("data:image"):
                continue

            if not img_url.startswith("http"):
                img_url = urljoin(article_url, img_url)

            return img_url

        return None
    except Exception as e:
        log(f"extract image from {article_url} failed: {e}", l=3)
        return None

def fetch_and_store_one_rss(journal, url, conn, cursor):
    feed = feedparser.parse(url)

    for entry in feed.entries:
        try:
            title = entry.title.strip()
            link = entry.link.strip()
            summary = entry.summary.strip() if "summary" in entry else ""
            published_time = entry.published

            cursor.execute('SELECT COUNT(*) FROM articles WHERE journal = ? AND title = ?', (journal, title))
            if cursor.fetchone()[0] > 0:
                continue

            log(title, published_time)
            summary = markdownify(summary)

            image_url = None
            if "media_content" in entry and entry.media_content:
                image_url = entry.media_content[0]["url"]
            elif "media_thumbnail" in entry and entry.media_thumbnail:
                image_url = entry.media_thumbnail[0]["url"]

            if not image_url:
                log(f"no image found for {title}, extracting from {link}")
                image_url = extract_image(link)

            log("image_url: %s"%image_url)

            cursor.execute('''
                INSERT OR IGNORE INTO articles (journal, title, link, summary, image_url, published_time, pushed_time)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (journal, title, link, summary, image_url, published_time, ""))
            conn.commit()

        except Exception as e:
            log(f"deal entry failed: {e}\n {entry}", l=3)

def fetch_and_store_rss():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()


    for journal, url in RSS_FEEDS.items():
        log("fetching rss feeds of %s"%journal)
        try:
            fetch_and_store_one_rss(journal, url, conn, cursor)
        except Exception as e:
            log(f"fetch {journal} rss feed failed: {e}", l=3)

    conn.close()

if __name__ == "__main__":
    init_db()
    fetch_and_store_rss()
