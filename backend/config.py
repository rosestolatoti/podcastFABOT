from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    PROJECT_NAME = "FABOT"
    VERSION = "2.0.0"

    # Sistema
    TTS_ENGINE = "Edge TTS"
    LLM_PROVIDER = "Groq (trocável)"
    DATABASE = "SQLite"
    DEBUG = os.getenv("DEBUG", "true").lower() == "true"

    KOKORO_URL = os.getenv("KOKORO_URL", "http://localhost:8880")

    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

    DATABASE_PATH = os.getenv(
        "DATABASE_PATH", str(BASE_DIR / "backend" / "db" / "fabot.db")
    )

    OUTPUT_DIR = os.getenv("OUTPUT_DIR", str(BASE_DIR / "data" / "output"))
    UPLOAD_DIR = os.getenv("UPLOAD_DIR", str(BASE_DIR / "data" / "uploads"))

    try:
        MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "50"))
    except ValueError:
        MAX_UPLOAD_MB = 50

    DEFAULT_LLM_MODE = os.getenv("DEFAULT_LLM_MODE", "glm")

    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
    GLM_API_KEY = os.getenv("GLM_API_KEY", "")

    CORS_ORIGINS = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    AUDIO_SAMPLE_RATE = 44100
    AUDIO_BITRATE = "192k"
    AUDIO_CHANNELS = 2

    LUFS_TARGET = -16.0
    CROSSFADE_MS = 30

    PAUSE_SAME_SPEAKER_MS = 250
    PAUSE_DIFFERENT_SPEAKER_MS = 700
    PAUSE_SHORT_MS = 600
    PAUSE_LONG_MS = 1400

    TTS_MAX_RETRIES = 3
    TTS_RETRY_DELAYS = [2, 4, 8]
    TTS_MAX_CONCURRENT = 3

    WORDS_PER_MINUTE = 140

    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = str(BASE_DIR / "logs" / "fabot.log")


settings = Settings()
