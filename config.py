"""
config.py - Configurações centralizadas (Render Free + GitHub Full Auto)
ICS sempre do GitHub repo (persistente GRÁTIS, sem Render Disk)
"""
import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


class BaseConfig:
    # Flask
    FLASK_ENV = os.getenv("FLASK_ENV", "production")
    DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"
    SECRET_KEY = os.getenv(
        "FLASK_SECRET_KEY",
        "dev-secret-key-change-in-production",
    )

    # Sessões
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = FLASK_ENV == "production"
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(
        minutes=int(os.getenv("SESSION_TIMEOUT_MINUTES", "120"))
    )

    # Caminhos / Storage
    # Render Free: sem /mnt/data (ephemeral storage)
    # Lê ficheiros do GitHub repo via raw.githubusercontent.com
    RENDER = os.getenv("RENDER", "true") == "true"
    REPO_PATH = os.getenv("REPO_PATH", "/opt/render/project/src")
    DATA_DIR = os.getenv("DATA_DIR", os.path.join(REPO_PATH, "data"))
    LOG_FILE = os.getenv("LOG_FILE", os.path.join(REPO_PATH, "sync.log"))

    # Caminhos locais (para manual_calendar.ics apenas)
    IMPORT_CALENDAR_PATH = os.path.join(REPO_PATH, "import_calendar.ics")
    MASTER_CALENDAR_PATH = os.path.join(REPO_PATH, "master_calendar.ics")
    MANUAL_CALENDAR_PATH = os.getenv(
        "MANUAL_CALENDAR_FILE",
        os.path.join(REPO_PATH, "manual_calendar.ics"),
    )

    # Autenticação Web
    ADMIN_USERNAME = os.getenv("WEB_USERNAME", "admin")
    ADMIN_PASSWORD = os.getenv("WEB_PASSWORD", "admin123")

    # Calendars (URLs)
    AIRBNB_ICAL_URL = os.getenv("AIRBNB_ICAL_URL", "")
    BOOKING_ICAL_URL = os.getenv("BOOKING_ICAL_URL", "")
    VRBO_ICAL_URL = os.getenv("VRBO_ICAL_URL", "")

    # Prep time
    BUFFER_DAYS_BEFORE = int(os.getenv("BUFFER_DAYS_BEFORE", "1"))
    BUFFER_DAYS_AFTER = int(os.getenv("BUFFER_DAYS_AFTER", "1"))

    # CORS
    CORS_ORIGINS = os.getenv(
        "CORS_ORIGINS",
        "rentalcalendarsync.onrender.com,localhost:5000,127.0.0.1:5000",
    )

    # Porta
    PORT = int(os.getenv("PORT", "8000"))

    # GitHub API
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
    GITHUB_OWNER = os.getenv("GITHUB_OWNER", "studioaxe")
    _raw_repo = os.getenv("GITHUB_REPO", "studioaxe/rcs")
    if "/" in _raw_repo:
        GITHUB_REPO = _raw_repo
    else:
        GITHUB_REPO = f"{GITHUB_OWNER}/{_raw_repo}"
    GITHUB_WORKFLOW = os.getenv("GITHUB_WORKFLOW", "full_auto_workflow.yml")
    GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")

    # ICS Source (SEMPRE "github" para Render Free)
    ICS_SOURCE = os.getenv("ICS_SOURCE", "github")

    # URLs GitHub Raw (para ler .ics do repo)
    # Formato: https://raw.githubusercontent.com/owner/repo/main/ficheiro.ics
    IMPORT_CALENDAR_URL = f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO.split('/')[-1]}/main/import_calendar.ics"
    MASTER_CALENDAR_URL = f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO.split('/')[-1]}/main/master_calendar.ics"

    # Email
    EMAIL_SERVER = os.getenv("EMAIL_SERVER", "smtp.gmail.com")
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
    EMAIL_USER = os.getenv("EMAIL_USER", "")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
    NOTIFICATION_EMAIL = os.getenv("NOTIFICATION_EMAIL", "")
    ERROR_EMAIL = os.getenv("ERROR_EMAIL", "")
    EMAIL_ON_ERROR = os.getenv("EMAIL_ON_ERROR", "true").lower() == "true"
    EMAIL_ATTACH_LOG = os.getenv("EMAIL_ATTACH_LOG", "true").lower() == "true"


class ProductionConfig(BaseConfig):
    FLASK_ENV = "production"
    DEBUG = False
    SESSION_COOKIE_SECURE = True


class DevelopmentConfig(BaseConfig):
    FLASK_ENV = "development"
    DEBUG = True


def get_config():
    env = os.getenv("FLASK_ENV", "production").lower()
    if env == "development":
        return DevelopmentConfig()
    return ProductionConfig()
