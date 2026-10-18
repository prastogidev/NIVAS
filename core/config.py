import os
from pathlib import Path
from dotenv import load_dotenv

# Load backend/.env file
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()


class Settings:
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # External API Keys (evaluated safely from environment)
    GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or None
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY") or None
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    OPENWEATHER_API_KEY: str | None = os.getenv("OPENWEATHER_API_KEY") or None
    GOOGLE_MAPS_API_KEY: str | None = os.getenv("GOOGLE_MAPS_API_KEY") or None
    AQICN_TOKEN: str | None = os.getenv("AQICN_TOKEN") or os.getenv("AQICN_API_KEY") or None
    PROPSTACK_API_KEY: str | None = os.getenv("PROPSTACK_API_KEY") or None
    DATA_GOV_IN_API_KEY: str | None = os.getenv("DATA_GOV_IN_API_KEY") or None


    # Local Paths
    MODEL_CHECKPOINT_DIR: str = os.getenv("MODEL_CHECKPOINT_DIR", "models/checkpoints")
    DATA_CACHE_DIR: str = os.getenv("DATA_CACHE_DIR", "data/cached_demo_data")


settings = Settings()
