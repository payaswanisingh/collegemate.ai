import logging
import os
import re
import joblib
from typing import Any


def set_logging(log_path: str = "logs/app.log", level: int = logging.INFO) -> None:
    """Configure rotating file logger.
    Creates the log directory if missing.
    """
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=5 * 1024 * 1024, backupCount=3
    )
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger = logging.getLogger()
    logger.setLevel(level)
    logger.addHandler(handler)
    # also output to console for interactive debugging
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)


def preprocess_text(text: str) -> str:
    """Lower‑case, remove punctuation, and collapse whitespace."""
    text = text.lower()
    text = re.sub(r"[\r\n]+", " ", text)
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def load_pickle(path: str) -> Any:
    """Load a pickle (or joblib) file safely."""
    return joblib.load(path)


def save_pickle(obj: Any, path: str) -> None:
    """Save an object using joblib for quick load/save."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    joblib.dump(obj, path)
