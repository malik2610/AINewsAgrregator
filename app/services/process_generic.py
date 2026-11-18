from typing import Optional
from app.scrapers.anthropic import AnthropicScraper
from app.database.repository import Repository
from .base import BaseProcessService


class GenericMarkdownProcessor(BaseProcessService):
    def __init__(self):
        super().__init__()
        self.scraper = AnthropicScraper()  # reuse url_to_markdown utility
        self.repo = Repository()

    def get_items_to_process(self, limit: Optional[int] = None) -> list:
        return self.repo.get_generic_articles_without_markdown(limit=limit)

    def process_item(self, item) -> Optional[str]:
        return self.scraper.url_to_markdown(item.url)

    def save_result(self, item, result: str) -> bool:
        return self.repo.update_generic_article_markdown(item.guid, result)


def process_generic_markdown(limit: Optional[int] = None) -> dict:
    processor = GenericMarkdownProcessor()
    return processor.process(limit=limit)


if __name__ == "__main__":
    result = process_generic_markdown()
    print(f"Total: {result['total']}")
    print(f"Processed: {result['processed']}")
    print(f"Failed: {result['failed']}")
