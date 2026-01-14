#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
config.py - Configurações Centralizadas (v3.2.4)

Alinhado com:
- backend/sync.py v3.2.4 (REPO_PATH = ".")
- backend/manual_editor_endpoints.py
- static/manual_editor.js

Desenvolvimento:
- LOCAL (testing): Caminhos locais relativos (".")
- RENDER (production): GitHub raw URLs para ICS persistente

Data: 13 de Janeiro de 2026
Desenvolvido por: PBrandão
"""

import os
from datetime import timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# BASE DIRECTORY
# ============================================================================

BASE_DIR = Path(__file__).resolve().parent


# ============================================================================
# BASE CONFIG CLASS
# ============================================================================

class BaseConfig:
    """Configurações base (comum a dev e production)"""

    # ========================================================================
    # FLASK
    # ========================================================================
    FLASK_ENV = os.getenv("FLASK_ENV", "production")
    DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"
    SECRET_KEY = os.getenv(
        "FLASK_SECRET_KEY",
        "dev-secret-key-change-in-production",
    )

    # ========================================================================
    # SESSÕES
    # ========================================================================
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = FLASK_ENV == "production"
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(
        minutes=int(os.getenv("SESSION_TIMEOUT_MINUTES", "120"))
    )

    # ========================================================================
    # CAMINHOS - ALINHADOS COM sync.py v3.2.4
    # ========================================================================
    # ✅ CRITICAL FIX v3.2.4: REPO_PATH = "." (raiz do repositório)
    REPO_PATH = os.getenv("REPO_PATH", ".")

    # Ficheiros ICS (raiz do repo)
    IMPORT_CALENDAR_PATH = os.path.join(REPO_PATH, "import_calendar.ics")
    MASTER_CALENDAR_PATH = os.path.join(REPO_PATH, "master_calendar.ics")
    MANUAL_CALENDAR_PATH = os.path.join(REPO_PATH, "manual_calendar.ics")

    # Log
    LOG_FILE = os.path.join(REPO_PATH, "sync.log")

    # ========================================================================
    # AUTENTICAÇÃO WEB
    # ========================================================================
    ADMIN_USERNAME = os.getenv("WEB_USERNAME", "admin")
    ADMIN_PASSWORD = os.getenv("WEB_PASSWORD", "admin123")

    # ========================================================================
    # CALENDÁRIOS (URLs de DOWNLOAD)
    # ========================================================================
    AIRBNB_ICAL_URL = os.getenv("AIRBNB_ICAL_URL", "")
    BOOKING_ICAL_URL = os.getenv("BOOKING_ICAL_URL", "")
    VRBO_ICAL_URL = os.getenv("VRBO_ICAL_URL", "")

    # ========================================================================
    # TEMPO DE PREPARAÇÃO (BUFFER DAYS)
    # ========================================================================
    BUFFER_DAYS_BEFORE = int(os.getenv("BUFFER_DAYS_BEFORE", "1"))
    BUFFER_DAYS_AFTER = int(os.getenv("BUFFER_DAYS_AFTER", "1"))

    # ========================================================================
    # CORS
    # ========================================================================
    CORS_ORIGINS = os.getenv(
        "CORS_ORIGINS",
        "rentalcalendarsync.onrender.com,localhost:5000,127.0.0.1:5000",
    )

    # ========================================================================
    # PORTA
    # ========================================================================
    PORT = int(os.getenv("PORT", "8000"))

    # ========================================================================
    # GITHUB API (para workflows dispatch)
    # ========================================================================
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
    GITHUB_OWNER = os.getenv("GITHUB_OWNER", "studioaxe")

    _raw_repo = os.getenv("GITHUB_REPO", "studioaxe/rcs")
    if "/" in _raw_repo:
        GITHUB_REPO = _raw_repo
    else:
        GITHUB_REPO = f"{GITHUB_OWNER}/{_raw_repo}"

    GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")

    # Workflows
    GITHUB_FULL_AUTO_WORKFLOW = "full_auto_workflow.yml"
    GITHUB_MANUAL_SYNC_WORKFLOW = "manual_sync_workflow.yml"

    # ========================================================================
    # NOTIFICAÇÕES / EMAIL
    # ========================================================================
    EMAIL_SERVER = os.getenv("EMAIL_SERVER", "smtp.gmail.com")
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
    EMAIL_USER = os.getenv("EMAIL_USER", "")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
    NOTIFICATION_EMAIL = os.getenv("NOTIFICATION_EMAIL", "")
    ERROR_EMAIL = os.getenv("ERROR_EMAIL", "")
    EMAIL_ON_ERROR = os.getenv("EMAIL_ON_ERROR", "true").lower() == "true"
    EMAIL_ATTACH_LOG = os.getenv("EMAIL_ATTACH_LOG", "true").lower() == "true"


# ============================================================================
# PRODUCTION CONFIG
# ============================================================================

class ProductionConfig(BaseConfig):
    """Configurações para produção (Render)"""
    FLASK_ENV = "production"
    DEBUG = False
    SESSION_COOKIE_SECURE = True


# ============================================================================
# DEVELOPMENT CONFIG
# ============================================================================

class DevelopmentConfig(BaseConfig):
    """Configurações para desenvolvimento (local)"""
    FLASK_ENV = "development"
    DEBUG = True
    SESSION_COOKIE_SECURE = False


# ============================================================================
# CONFIG FACTORY
# ============================================================================

def get_config():
    """Factory function para obter configuração correcta"""
    env = os.getenv("FLASK_ENV", "production").lower()
    if env == "development":
        return DevelopmentConfig()
    return ProductionConfig()
