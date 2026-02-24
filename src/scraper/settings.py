BOT_NAME = "sovereignlens"

SPIDER_MODULES = ["src.scraper.spiders"]
NEWSPIDER_MODULE = "src.scraper.spiders"

USER_AGENT = (
    "SovereignLens/0.1 AI Policy Research Bot "
    "(+https://github.com/PareboAI/sovereignlens)"
)

ROBOTSTXT_OBEY = True

# Polite crawling: one request per 2 seconds, one concurrent request per domain
DOWNLOAD_DELAY = 2
CONCURRENT_REQUESTS = 8
CONCURRENT_REQUESTS_PER_DOMAIN = 1

# Retry on transient errors; don't hammer the server
RETRY_TIMES = 2
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]

ITEM_PIPELINES = {
    "src.scraper.pipelines.PostgresPipeline": 300,
}

# Scrapy's own log output; our code uses loguru directly
LOG_LEVEL = "WARNING"
