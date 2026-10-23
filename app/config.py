from pathlib import Path

from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

BROWSER_PROFILE_DIR = BASE_DIR / "browser_profile"

# Playwright (BROWSER_CHANNEL=chrome локально; в Docker оставьте пустым — bundled Chromium)
HEADLESS = False
BROWSER_CHANNEL = os.getenv("BROWSER_CHANNEL", "chrome").strip()
NAVIGATION_TIMEOUT_MS = 30_000
ACTION_DELAY_MS = 800
CAPTCHA_WAIT_MS = 120_000
HEADED_CLOSE_DELAY_MS = 3_000

# Google SERP
DEFAULT_MAX_PAGES = 3
RESULTS_PER_PAGE = 10

# Yandex Maps — max_pages = число прокруток списка организаций
MAPS_SCROLL_PAUSE_MS = 1500

# Supabase / PostgreSQL
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

# Batch search
MAX_BATCH_CITIES = 30
CITIES_FILE = BASE_DIR / "data" / "cities.json"

# Proxies (через запятую или с новой строки): http://user:pass@host:port
PROXY_LIST = os.getenv("PROXY_LIST", "").strip()
PROXY_USE_DIRECT = os.getenv("PROXY_USE_DIRECT", "true").strip().lower() in {"1", "true", "yes"}

# Apify fallback после N подряд неудачных раундов (все прокси + direct)
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN", "").strip()
APIFY_FALLBACK_THRESHOLD = int(os.getenv("APIFY_FALLBACK_THRESHOLD", "5"))
APIFY_GOOGLE_ACTOR = os.getenv("APIFY_GOOGLE_ACTOR", "apify/google-search-scraper").strip()
APIFY_YANDEX_ACTOR = os.getenv("APIFY_YANDEX_ACTOR", "johnvc/Scrape-Yandex").strip()
APIFY_YANDEX_MAPS_ACTOR = os.getenv(
    "APIFY_YANDEX_MAPS_ACTOR", "zen-studio/yandex-maps-scraper"
).strip()

# LLM (OpenAI-compatible: OpenAI, OpenRouter, local proxy)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
LLM_RAW_TEXT_MAX_CHARS = int(os.getenv("LLM_RAW_TEXT_MAX_CHARS", "4000"))
