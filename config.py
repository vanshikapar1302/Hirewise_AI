# import os
# from pathlib import Path
# from dotenv import load_dotenv

# # Base Directory of the Project
# BASE_DIR = Path(__file__).resolve().parent

# # Load environment variables from .env file if it exists
# load_dotenv(BASE_DIR / ".env")

# class Config:
#     BASE_DIR = BASE_DIR
#     # Flask Settings
#     SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "hirewise_secure_fallback_secret_key_2026")
#     ENV = os.environ.get("FLASK_ENV", "development")
#     DEBUG = ENV == "development"

#     # Database Settings
#     db_url = os.environ.get("DATABASE_URL")

#     print("DATABASE_URL from env:", os.environ.get("DATABASE_URL"))
#     print("Final DB URI before processing:", db_url)

#     if db_url:
#         if db_url.startswith("postgres://"):
#             db_url = db_url.replace("postgres://", "postgresql://", 1)

#         print("Final DB URI after processing:", db_url)
#         SQLALCHEMY_DATABASE_URI = db_url
#     else:
#         raise ValueError("[ERROR] DATABASE_URL is missing. SQLite fallback is disabled by configuration rules.")
    
#     SQLALCHEMY_TRACK_MODIFICATIONS = False

#     # Uploads Configuration
#     UPLOAD_FOLDER = BASE_DIR / "uploads"
#     UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
#     ALLOWED_EXTENSIONS = {"pdf", "wav", "webm", "mp4", "mp3"}
#     # Max file size: 30MB
#     MAX_CONTENT_LENGTH = 30 * 1024 * 1024

#     GROQ_API_KEY = os.environ.get("GROQ_API_KEY") or ""
#     CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY") or os.environ.get("ANTHROPIC_API_KEY") or ""
    
#     # Whisper settings
#     WHISPER_MODEL_NAME = os.environ.get("WHISPER_MODEL_NAME", "tiny")

#     # Mail Server Configuration
#     MAIL_SERVER = os.environ.get("MAIL_SERVER", "")
#     MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
#     MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
#     MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
#     MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "True").lower() in ("true", "1", "yes")
#     ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@hirewise.ai")
import os
from pathlib import Path
from dotenv import load_dotenv

# Base Directory of the Project
BASE_DIR = Path(__file__).resolve().parent

# Load environment variables from .env file if it exists
load_dotenv(BASE_DIR / ".env")


class Config:
    BASE_DIR = BASE_DIR

    # Flask Settings
    SECRET_KEY = os.environ.get(
        "FLASK_SECRET_KEY",
        "hirewise_secure_fallback_secret_key_2026"
    )
    ENV = os.environ.get("FLASK_ENV", "development")
    DEBUG = ENV == "development"

    # Database Settings
    db_url = os.environ.get("DATABASE_URL")

    print("DATABASE_URL from env:", bool(db_url))

    if db_url:
        if db_url.startswith("postgres://"):
            db_url = db_url.replace(
                "postgres://",
                "postgresql://",
                1
            )

        print("Using Supabase/PostgreSQL database")
        SQLALCHEMY_DATABASE_URI = db_url

    else:
        raise ValueError("[ERROR] DATABASE_URL is missing. SQLite fallback is disabled by configuration rules.")

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Uploads Configuration
    UPLOAD_FOLDER = BASE_DIR / "uploads"
    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

    ALLOWED_EXTENSIONS = {"pdf", "wav", "webm", "mp4", "mp3"}

    # Max file size: 30 MB
    MAX_CONTENT_LENGTH = 30 * 1024 * 1024

    # API Keys
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
    CLAUDE_API_KEY = (
        os.environ.get("CLAUDE_API_KEY")
        or os.environ.get("ANTHROPIC_API_KEY")
        or ""
    )

    # Whisper Settings
    WHISPER_MODEL_NAME = os.environ.get(
        "WHISPER_MODEL_NAME",
        "tiny"
    )

    # Mail Server Configuration
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_USE_TLS = (
        os.environ.get("MAIL_USE_TLS", "True").lower()
        in ("true", "1", "yes")
    )
    ADMIN_EMAIL = os.environ.get(
        "ADMIN_EMAIL",
        "admin@hirewise.ai"
    )