"""Configuration: reads environment variables and an optional .env file (no extra dependency)."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_dotenv(path):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load():
    _load_dotenv(os.path.join(ROOT, ".env"))
    return {
        "SECRET_KEY": os.environ.get("SECRET_KEY", "dev-only-change-me"),
        "DATABASE": os.environ.get("DATABASE_PATH", os.path.join(ROOT, "database", "amatashield.db")),
        "UPLOAD_DIR": os.environ.get("UPLOAD_DIR", os.path.join(ROOT, "uploads")),
        "MAX_CONTENT_LENGTH": int(os.environ.get("MAX_UPLOAD_MB", "8")) * 1024 * 1024,
        "GEMINI_API_KEY": os.environ.get("GEMINI_API_KEY", ""),
        "GEMINI_MODEL": os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
        "SESSION_COOKIE_SECURE": os.environ.get("SESSION_COOKIE_SECURE", "0") == "1",
        "SESSION_COOKIE_SAMESITE": "Lax",
        "SESSION_COOKIE_HTTPONLY": True,
    }
