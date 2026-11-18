from typing import List, Optional
from .base import BaseScraper, Article

COMPANY_RSS_FEEDS: dict[str, List[str]] = {
    "openai": [
        "https://openai.com/news/rss.xml",
    ],
    "anthropic": [
        "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_news.xml",
        "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_research.xml",
        "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_engineering.xml",
    ],
    "google_ai": [
        "https://blog.google/technology/ai/rss/",
    ],
    "deepmind": [
        "https://deepmind.google/blog/rss.xml",
    ],
    "meta_ai": [
        "https://ai.meta.com/blog/rss/",
    ],
    "nvidia": [
        "https://nvidianews.nvidia.com/rss/all.xml",
    ],
    "microsoft": [
        "https://blogs.microsoft.com/ai/feed/",
    ],
    "huggingface": [
        "https://huggingface.co/blog/feed.xml",
    ],
    "mistral": [
        "https://mistral.ai/feed.xml",
    ],
    "cohere": [
        "https://cohere.com/blog/rss",
    ],
    "stability_ai": [
        "https://stability.ai/news/rss.xml",
    ],
    "groq": [
        "https://groq.com/feed/",
    ],
}

# reverse map: feed_url -> company name (for tagging articles)
_URL_TO_COMPANY = {
    url: company
    for company, urls in COMPANY_RSS_FEEDS.items()
    for url in urls
}


class GenericArticle(Article):
    company: str


class GenericScraper(BaseScraper):
    def __init__(self, companies: Optional[List[str]] = None):
        self.companies = companies or list(COMPANY_RSS_FEEDS.keys())

    @property
    def rss_urls(self) -> List[str]:
        urls = []
        for company in self.companies:
            urls.extend(COMPANY_RSS_FEEDS.get(company, []))
        return urls

    def get_articles(self, hours: int = 24) -> List[GenericArticle]:
        import feedparser
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=hours)
        articles = []
        seen_guids = set()

        for rss_url in self.rss_urls:
            company = _URL_TO_COMPANY.get(rss_url, "unknown")
            feed = feedparser.parse(rss_url)
            if not feed.entries:
                continue

            for entry in feed.entries:
                published_parsed = getattr(entry, "published_parsed", None)
                if not published_parsed:
                    continue

                published_time = datetime(*published_parsed[:6], tzinfo=timezone.utc)
                if published_time < cutoff:
                    continue

                guid = entry.get("id", entry.get("link", ""))
                if guid in seen_guids:
                    continue

                seen_guids.add(guid)
                articles.append(
                    GenericArticle(
                        title=entry.get("title", ""),
                        description=entry.get("description", ""),
                        url=entry.get("link", ""),
                        guid=guid,
                        published_at=published_time,
                        category=entry.get("tags", [{}])[0].get("term") if entry.get("tags") else None,
                        company=company,
                    )
                )

        return articles


if __name__ == "__main__":
    scraper = GenericScraper()
    articles = scraper.get_articles(hours=72)
    for a in articles:
        print(f"[{a.company}] {a.title} — {a.published_at.date()}")
