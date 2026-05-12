import os
import feedparser
from datetime import datetime, timedelta, timezone
from dateutil import parser
from notion_client import Client

# =========================
# ENV VARIABLES (Render)
# =========================
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")
CONTROL_DB_ID = os.getenv("CONTROL_DB_ID")

notion = Client(auth=NOTION_TOKEN)

# =========================
# FETCH CONTROL SETTINGS
# =========================
def get_control_settings():
    response = notion.databases.query(database_id=CONTROL_DB_ID)

    page = response["results"][0]
    props = page["properties"]

    run_now = props["Run Now"]["checkbox"]
    lookback_days = props["Lookback Days"]["number"] or 7

    return run_now, lookback_days, page["id"]

# =========================
# UPDATE CONTROL (RESET RUN)
# =========================
def reset_run_flag(page_id):
    notion.pages.update(
        page_id=page_id,
        properties={
            "Run Now": {"checkbox": False},
            "Last Run": {"date": {"start": datetime.now(timezone.utc).isoformat()}}
        }
    )

# =========================
# RSS FEEDS
# =========================
feeds = [
    "https://economictimes.indiatimes.com/rssfeeds/13352306.cms",
    "https://www.business-standard.com/rss/home_page_top_stories.rss",
    "https://news.google.com/rss/search?q=M%26A+India&hl=en-IN&gl=IN&ceid=IN:en",
    "https://entrackr.com/feed/",
    "https://inc42.com/feed",
    "https://yourstory.com/feed",
    "https://www.vccircle.com/feed"
]

keywords = [
    "acquire", "acquisition", "buy", "stake",
    "invest", "funding", "raise", "merger",
    "deal", "venture", "ipo"
]

# =========================
# PUSH TO NOTION
# =========================
def push_to_notion(title, summary, link, source, article_date):

    notion.pages.create(
        parent={"database_id": DATABASE_ID},
        properties={
            "Deal Name": {
                "title": [{"text": {"content": title}}]
            },
            "Raw Title": {
                "rich_text": [{"text": {"content": title}}]
            },
            "Raw Description": {
                "rich_text": [{"text": {"content": summary[:2000]}}]
            },
            "Source": {
                "rich_text": [{"text": {"content": source}}]
            },
            "Source Link": {
                "url": link
            },
            "Date Added": {
                "date": {"start": datetime.now(timezone.utc).isoformat()}
            },
            "Published Date": {
                "date": {"start": article_date.isoformat()}
            },
            "Status": {
                "select": {"name": "Raw"}
            }
        }
    )

# =========================
# MAIN RUN FUNCTION
# =========================
def run_scraper(lookback_days):

    today = datetime.now(timezone.utc)
    cutoff = today - timedelta(days=lookback_days)

    seen_titles = set()

    for feed_url in feeds:

        feed = feedparser.parse(feed_url)

        for article in feed.entries:

            try:
                published = article.get("published", article.get("updated"))
                if not published:
                    continue

                article_date = parser.parse(published)

                if article_date.tzinfo is None:
                    article_date = article_date.replace(tzinfo=timezone.utc)
                else:
                    article_date = article_date.astimezone(timezone.utc)

            except:
                continue

            if article_date < cutoff:
                continue

            title = article.title
            summary = article.get("summary", "")

            if title in seen_titles:
                continue
            seen_titles.add(title)

            text = (title + summary).lower()

            if not any(k in text for k in keywords):
                continue

            push_to_notion(title, summary, article.link, feed_url, article_date)

    print("✅ DONE")

# =========================
# ENTRY POINT
# =========================
if __name__ == "__main__":

    run_now, lookback_days, page_id = get_control_settings()

    if run_now:
        print("🚀 Running scraper...")
        run_scraper(lookback_days)
        reset_run_flag(page_id)

    else:
        print("⏳ No run triggered")