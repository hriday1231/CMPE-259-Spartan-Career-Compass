import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent
CAREER_GUIDES_DIR = PROJECT_ROOT / "career_guides"

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/career_compass")

ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID", "")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY", "")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_LARGE_MODEL = os.getenv("OLLAMA_LARGE_MODEL", "llama2:13b")
OLLAMA_SMALL_MODEL = os.getenv("OLLAMA_SMALL_MODEL", "mistral:7b")