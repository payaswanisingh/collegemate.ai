"""
Flask application configuration for CampusMate AI Student Portal.

Environment-specific settings live here. External JSON configuration
(university departments, semesters, etc.) is loaded exclusively through
``config_loader`` — never read JSON files directly elsewhere in the app.
"""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root when present (local development).
load_dotenv()

# ---------------------------------------------------------------------------
# Base paths
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
UPLOAD_DIR = BASE_DIR / "uploads" / "profiles"


class Config:
    """Default Flask configuration shared across environments."""

    # ------------------------------------------------------------------
    # Core Flask
    # ------------------------------------------------------------------

    # Session signing — MUST be overridden in production via SECRET_KEY env var.
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-only-change-me-in-production")

    # Disable Flask-SQLAlchemy modification tracking (saves memory, not needed).
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False

    # SQLite database stored outside source control (instance/ folder).
    SQLALCHEMY_DATABASE_URI: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{INSTANCE_DIR / 'campusmate.db'}",
    )

    # ------------------------------------------------------------------
    # Sessions & authentication cookies
    # ------------------------------------------------------------------

    # Duration for "Remember Me" sessions (30 days).
    REMEMBER_COOKIE_DURATION: timedelta = timedelta(days=30)
    PERMANENT_SESSION_LIFETIME: timedelta = timedelta(days=30)

    # Cookie security — enable SECURE cookies in production (HTTPS).
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "Lax"
    SESSION_COOKIE_SECURE: bool = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"

    REMEMBER_COOKIE_HTTPONLY: bool = True
    REMEMBER_COOKIE_SAMESITE: str = "Lax"
    REMEMBER_COOKIE_SECURE: bool = SESSION_COOKIE_SECURE

    # ------------------------------------------------------------------
    # File uploads (profile pictures)
    # ------------------------------------------------------------------

    MAX_CONTENT_LENGTH: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "2")) * 1024 * 1024
    UPLOAD_FOLDER: str = str(UPLOAD_DIR)
    ALLOWED_PROFILE_EXTENSIONS: frozenset[str] = frozenset({"png", "jpg", "jpeg", "webp", "gif"})

    # ------------------------------------------------------------------
    # External configuration paths
    # ------------------------------------------------------------------

    # Path to university.json — override to support different colleges.
    UNIVERSITY_CONFIG_PATH: str = os.getenv(
        "UNIVERSITY_CONFIG_PATH",
        str(BASE_DIR / "config" / "university.json"),
    )

    # ------------------------------------------------------------------
    # Portal branding (overridable per deployment)
    # ------------------------------------------------------------------

    APP_NAME: str = os.getenv("APP_NAME", "CampusMate AI")
    APP_TAGLINE: str = os.getenv("APP_TAGLINE", "Your Smart Campus Assistant")

    # ------------------------------------------------------------------
    # Note: Gemini configuration (GEMINI_API_KEY, GEMINI_MODEL)
    # ------------------------------------------------------------------
    # Intentionally NOT read here. `Chatbot` (chatbot.py) is instantiated
    # directly with no reference to the Flask app or this Config class, so
    # it loads GEMINI_API_KEY / GEMINI_MODEL itself via python-dotenv at
    # startup. This is by design, not an oversight — if Gemini ever needs
    # to be reachable from Config for some other reason (e.g. a health
    # check route), read the same two env vars here rather than moving
    # Chatbot's initialization to depend on this class.


class DevelopmentConfig(Config):
    """Local development settings."""

    DEBUG: bool = True
    TESTING: bool = False


class ProductionConfig(Config):
    """Production settings — stricter defaults."""

    DEBUG: bool = False
    TESTING: bool = False
    SESSION_COOKIE_SECURE: bool = True
    REMEMBER_COOKIE_SECURE: bool = True


class TestingConfig(Config):
    """In-memory database for automated tests."""

    TESTING: bool = True
    DEBUG: bool = True
    SQLALCHEMY_DATABASE_URI: str = "sqlite:///:memory:"
    WTF_CSRF_ENABLED: bool = False  # reserved if WTForms is added later


# Registry used by create_app() to pick the active config class.
config_by_name: dict[str, type[Config]] = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}


def get_config() -> type[Config]:
    """Return the config class for the current FLASK_ENV / FLASK_CONFIG."""
    env_name = os.getenv("FLASK_CONFIG") or os.getenv("FLASK_ENV", "development")
    return config_by_name.get(env_name, DevelopmentConfig)
