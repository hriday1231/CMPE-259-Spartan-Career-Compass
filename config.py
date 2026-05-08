import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
CAREER_GUIDES_DIR = PROJECT_ROOT / "career_guides"

# .env is loaded relative to this file, not the caller's cwd
load_dotenv(PROJECT_ROOT / ".env")

DB_PATH = Path(os.getenv("DB_PATH", str(PROJECT_ROOT / "data" / "career_compass.db")))

ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID", "")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY", "")
ADZUNA_COUNTRY = os.getenv("ADZUNA_COUNTRY", "us")

BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_LARGE_MODEL = os.getenv("OLLAMA_LARGE_MODEL", "llama2:13b")
OLLAMA_SMALL_MODEL = os.getenv("OLLAMA_SMALL_MODEL", "mistral:7b")

PROMPT_CACHE_PATH = PROJECT_ROOT / ".cache" / "prompt_cache.sqlite"
