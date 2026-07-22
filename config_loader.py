"""
Centralized configuration file loader for CampusMate AI.

This is the single entry point for reading and validating all external
configuration files (JSON). Application code should import from here rather
than opening config files directly.

Usage:
    from config_loader import load_university_config, ConfigurationError
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths — JSON data lives in the config/ directory (not a Python package).
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_DATA_DIR = PROJECT_ROOT / "config"
DEFAULT_UNIVERSITY_CONFIG_PATH = CONFIG_DATA_DIR / "university.json"

# Required top-level keys that must be non-empty arrays.
_REQUIRED_LIST_FIELDS = ("departments", "semesters")

# Optional list fields reserved for future portal features.
_OPTIONAL_LIST_FIELDS = (
    "academic_years",
    "sections",
    "degree_programs",
    "campuses",
)


class ConfigurationError(Exception):
    """Raised when a configuration file is missing, unreadable, or invalid."""


def _validate_non_empty_string_list(
    data: dict[str, Any],
    field: str,
    *,
    required: bool,
    config_path: Path,
) -> list[str]:
    """Ensure *field* is a list of non-empty strings."""
    if field not in data:
        if required:
            raise ConfigurationError(
                f"Configuration error in '{config_path}': "
                f"missing required field '{field}'."
            )
        return []

    value = data[field]
    if not isinstance(value, list):
        raise ConfigurationError(
            f"Configuration error in '{config_path}': "
            f"'{field}' must be an array, got {type(value).__name__}."
        )

    cleaned: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ConfigurationError(
                f"Configuration error in '{config_path}': "
                f"'{field}[{index}]' must be a non-empty string."
            )
        cleaned.append(item.strip())

    if required and not cleaned:
        raise ConfigurationError(
            f"Configuration error in '{config_path}': "
            f"'{field}' must contain at least one entry."
        )

    return cleaned


def load_university_config(
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    """
    Load and validate university configuration from JSON.

    Returns a normalized dict with guaranteed ``departments`` and ``semesters``
    lists. Optional future fields are included when present.

    Raises:
        ConfigurationError: If the file is missing, malformed, or invalid.
    """
    path = Path(config_path) if config_path else DEFAULT_UNIVERSITY_CONFIG_PATH
    path = path.resolve()

    if not path.is_file():
        raise ConfigurationError(
            f"University configuration file not found: '{path}'. "
            "Ensure config/university.json exists or set UNIVERSITY_CONFIG_PATH."
        )

    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigurationError(
            f"Unable to read university configuration '{path}': {exc}"
        ) from exc

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ConfigurationError(
            f"Invalid JSON in university configuration '{path}': {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise ConfigurationError(
            f"Configuration error in '{path}': root value must be a JSON object."
        )

    normalized: dict[str, Any] = {}

    college = data.get("college")
    if college is not None:
        if not isinstance(college, dict):
            raise ConfigurationError(
                f"Configuration error in '{path}': 'college' must be an object."
            )
        normalized["college"] = {
            "name": str(college.get("name", "Default University")).strip(),
            "slug": str(college.get("slug", "default")).strip(),
        }

    for field in _REQUIRED_LIST_FIELDS:
        normalized[field] = _validate_non_empty_string_list(
            data, field, required=True, config_path=path
        )

    for field in _OPTIONAL_LIST_FIELDS:
        if field in data:
            normalized[field] = _validate_non_empty_string_list(
                data, field, required=False, config_path=path
            )
        else:
            normalized[field] = []

    reserved = {"college", *_REQUIRED_LIST_FIELDS, *_OPTIONAL_LIST_FIELDS}
    for key, value in data.items():
        if key not in reserved:
            normalized[key] = value

    return normalized


def get_university_config_path() -> Path:
    """Return the resolved path to the active university config file."""
    env_path = os.getenv("UNIVERSITY_CONFIG_PATH")
    if env_path:
        return Path(env_path).resolve()
    return DEFAULT_UNIVERSITY_CONFIG_PATH
