#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
config.py - Configuration Management

Versão: 1.0 Final
Data: 02 de fevereiro de 2026
Desenvolvido por: PBrandão
"""

import os

from dotenv import load_dotenv

from pathlib import Path

# Load environment variables from .env
load_dotenv()

class Config:
    """Base configuration."""

    # Flask
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'rental-calendar-sync-secret-key-2026')
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    FLASK_PORT = int(os.getenv('FLASK_PORT', 8000))
    DEBUG = FLASK_ENV == 'development'

    # Session
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = 604800 # 7 days in seconds

    # CORS
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*').split(',')

    # Authentication
    ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')

    # Git
    GIT_USER_EMAIL = os.getenv('GIT_USER_EMAIL', 'rental-calendar-sync@pbrandao.pt')
    GIT_USER_NAME = os.getenv('GIT_USER_NAME', 'Rental Calendar Bot')
    GIT_BRANCH = os.getenv('GIT_BRANCH', 'main')

    # GitHub
    GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', '')
    GITHUB_REPO = os.getenv('GITHUB_REPO', 'studioaxe/rcs')

    # Calendars
    IMPORT_CALENDAR_PATH = os.getenv('IMPORT_CALENDAR_PATH', 'import_calendar.ics')
    MANUAL_CALENDAR_PATH = os.getenv('MANUAL_CALENDAR_PATH', 'manual_calendar.ics')
    MASTER_CALENDAR_PATH = os.getenv('MASTER_CALENDAR_PATH', 'master_calendar.ics')

    # Timezone
    TIMEZONE = os.getenv('TIMEZONE', 'Europe/Lisbon')

    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'rental_calendar_sync.log')

    # Features
    ENABLE_NOTIFICATIONS = os.getenv('ENABLE_NOTIFICATIONS', 'true').lower() == 'true'
    ENABLE_AUTO_SYNC = os.getenv('ENABLE_AUTO_SYNC', 'true').lower() == 'true'
    AUTO_SYNC_INTERVAL = int(os.getenv('AUTO_SYNC_INTERVAL', 21600)) # 6 hours

    # ========================================================================
    # EMAIL / NOTIFICAÇÕES (ADICIONADO EM 19 DE JANEIRO DE 2026)
    # ========================================================================

    EMAIL_SERVER = os.getenv("EMAIL_SERVER", "smtp.gmail.com")
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
    EMAIL_USER = os.getenv("EMAIL_USER", "")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
    NOTIFICATION_EMAIL = os.getenv("NOTIFICATION_EMAIL", "")
    ERROR_EMAIL = os.getenv("ERROR_EMAIL", "")
    EMAIL_NOTIFIER_ENABLED = os.getenv("EMAIL_NOTIFIER_ENABLED", "false").lower() == "true"
    EMAIL_ATTACH_LOG = os.getenv("EMAIL_ATTACH_LOG", "true").lower() == "true"

    @classmethod
    def get_config(cls):
        """Get current configuration."""
        return cls()


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    TESTING = False


class TestingConfig(Config):
    """Testing configuration."""
    DEBUG = True
    TESTING = True
    SESSION_PERMANENT = False


def get_config():
    """Get appropriate configuration based on FLASK_ENV."""
    env = os.getenv('FLASK_ENV', 'development')

    if env == 'production':
        return ProductionConfig()
    elif env == 'testing':
        return TestingConfig()
    else:
        return DevelopmentConfig()


# Verify required files/directories exist
def verify_setup() -> bool:
    """Verify setup is complete."""

def verify_setup():
    """Verify setup is complete."""
    required_files = [
        'import_calendar.ics',
        'manual_calendar.ics',
    ]

    required_dirs = [
        'backend',
        'static',
        'templates',
    ]

    errors = []

    for file in required_files:
        if not os.path.exists(file):
            errors.append(f"⚠️ Missing file: {file}")

    for dir in required_dirs:
        if not os.path.exists(dir):
            errors.append(f"⚠️ Missing directory: {dir}")

    if os.getenv('FLASK_ENV') == 'production':
        if not os.getenv('GITHUB_TOKEN'):
            errors.append("⚠️ GITHUB_TOKEN not set (required for git push)")

    if errors:
        print("\nSetup Verification Warnings:")
        for error in errors:
            print(f" {error}")
        return False

    return True


# Log configuration on import

if __name__ != '__main__':
    cfg = get_config()
    print(f"✅ Configuration loaded: {cfg.FLASK_ENV}")
    print(f"   Port: {cfg.FLASK_PORT}")
    print(f"   Debug: {cfg.DEBUG}")
