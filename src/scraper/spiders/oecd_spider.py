import re

import scrapy
from loguru import logger
from scrapy.http import Response

from src.scraper.spiders.base_scraper import BaseScraper

# Matches article pages like https://oecd.ai/en/wonk/some-article-slug
_ARTICLE_URL_RE = re.compile(r"oecd\.ai/en/wonk/[^/]+$")

# Date patterns commonly found in inline text (e.g. "June 10, 2020" or "2020-06-10")
_DATE_RE = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+\d{1,2},?\s+\d{4}\b"
    r"|\b\d{4}-\d{2}-\d{2}\b"
)

# Parenthesised country in author affiliation, e.g. "NIC.br (Brazil)"
_COUNTRY_PAREN_RE = re.compile(r"\(([A-Za-z][A-Za-z\s]{2,})\)")


class OECDAISpider(scrapy.Spider):
    name = "oecd_ai"

    # Primary entry point as required; post sitemap for comprehensive coverage.
    start_urls = [
        "https://oecd.ai/en/dashboards/policy-areas",
        "https://oecd.ai/sitemaps/wonk/post-sitemap.xml",
    ]

    def parse(self, response: Response):
        if "sitemap" in response.url:
            yield from self._parse_sitemap(response)
        else:
            yield from self._parse_page(response)

    # ------------------------------------------------------------------
    # Discovery helpers
    # ------------------------------------------------------------------

    def _parse_sitemap(self, response: Response):
        """Extract article URLs from the WordPress post sitemap."""
        response.selector.remove_namespaces()
        urls = response.css("url > loc::text").getall()
        logger.info(f"Sitemap {response.url}: found {len(urls)} URLs")
        for url in urls:
            if _ARTICLE_URL_RE.search(url):
                yield scrapy.Request(url, callback=self.parse_article, errback=self._handle_error)

    def _parse_page(self, response: Response):
        """Follow /en/wonk/ links present in any crawled page."""
        hrefs = response.css("a::attr(href)").getall()
        for href in hrefs:
            if "/en/wonk/" in href:
                full_url = response.urljoin(href)
                if _ARTICLE_URL_RE.search(full_url):
                    yield scrapy.Request(
                        full_url, callback=self.parse_article, errback=self._handle_error
                    )

    # ------------------------------------------------------------------
    # Article extraction
    # ------------------------------------------------------------------

    def parse_article(self, response: Response):
        if response.status != 200:
            logger.warning(f"HTTP {response.status}: {response.url}")
            return

        title = self._extract_title(response)
        if not title:
            logger.debug(f"No title found, skipping: {response.url}")
            return

        content = self._extract_content(response)
        country = self._extract_country(response)

        yield {
            "title": title,
            "source_url": response.url,
            "content": content or title,
            "country": country,
            "source_name": "oecd_ai",
        }

    # ------------------------------------------------------------------
    # Field extractors
    # ------------------------------------------------------------------

    def _extract_title(self, response: Response) -> str:
        # h1 is always present in SSR'd article pages
        title = response.css("h1::text").get("").strip()
        if not title:
            # Fallback: Open Graph title
            title = response.css("meta[property='og:title']::attr(content)").get("").strip()
        return title

    def _extract_content(self, response: Response) -> str:
        # Prefer article body text; fall back to OG description
        parts = response.css(
            ".article p::text, .article h2::text, .article h3::text, .article li::text,"
            " article p::text, article h2::text, article li::text"
        ).getall()
        content = " ".join(p.strip() for p in parts if p.strip())

        if not content:
            content = response.css("meta[property='og:description']::attr(content)").get("") or ""

        return content.strip()

    def _extract_country(self, response: Response) -> str | None:
        # 1. Parenthesised country in author affiliation, e.g. "NIC.br (Brazil)"
        for affiliation in response.css(".card--author p::text").getall():
            m = _COUNTRY_PAREN_RE.search(affiliation)
            if m:
                return m.group(1).strip()

        # 2. Explicit geo meta tag (unlikely on these pages, but free to check)
        geo = response.css("meta[name='geo.placename']::attr(content)").get()
        if geo:
            return geo.strip()

        # 3. Article tags that look like country names (title-cased, not all-caps, 4+ chars)
        for tag in response.css(".article__tags a::text, .tags a::text, .tag::text").getall():
            tag = tag.strip()
            if tag and len(tag) >= 4 and tag[0].isupper() and not tag.isupper():
                return tag

        return None

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    def _handle_error(self, failure):
        logger.error(f"Request failed [{failure.value}]: {failure.request.url}")


# ---------------------------------------------------------------------------
# BaseScraper-compatible adapter
# ---------------------------------------------------------------------------


class OECDScraper(BaseScraper):
    """Wraps OECDAISpider so it can be driven by the same run/save_to_db
    interface as the other BaseScraper subclasses.

    The Scrapy CrawlerProcess is run with the PostgresPipeline disabled;
    items are collected via the item_scraped signal and returned from run()
    so that BaseScraper.save_to_db() handles all persistence uniformly.
    """

    source_name = "oecd_ai"

    def run(self) -> list[dict]:
        from scrapy import signals
        from scrapy.crawler import CrawlerProcess

        import src.scraper.settings as _s

        collected: list[dict] = []

        settings = {k: getattr(_s, k) for k in dir(_s) if k.isupper()}
        settings["ITEM_PIPELINES"] = {}  # Disable pipeline; save_to_db handles persistence

        process = CrawlerProcess(settings=settings)
        crawler = process.create_crawler(OECDAISpider)

        def item_scraped(item, response, spider):
            collected.append(dict(item))

        crawler.signals.connect(item_scraped, signal=signals.item_scraped)
        process.crawl(crawler)
        process.start()

        logger.info(f"OECD spider collected {len(collected)} items")
        return collected
