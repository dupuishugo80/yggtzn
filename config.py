import os
from dotenv import load_dotenv

load_dotenv()

YGG_USERNAME = os.getenv("YGG_USERNAME", "")
YGG_PASSWORD = os.getenv("YGG_PASSWORD", "")
API_KEY = os.getenv("API_KEY", "changeme")
HEADLESS = os.getenv("HEADLESS", "true").lower() in ("true", "1", "yes")
MAX_SEARCH_PAGES = int(os.getenv("MAX_SEARCH_PAGES", "3"))
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")
DEBUG = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
YGG_BASE_URL = "https://www.yggtorrent.org"
