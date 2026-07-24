
"""Utility module for the AI Student Support Chatbot backend.
Provides functions for:
- Loading the CSV dataset
- Text preprocessing (lowercasing, stripping)
- Vectorizing text using TF‑IDF
- Encoding categorical labels
- Saving and loading PyTorch model checkpoints and auxiliary artifacts
- Determining the appropriate torch device
"""

import os
import pandas as pd
import numpy as np
import joblib
from typing import Tuple, Any

# NLP libraries
import nltk
from nltk.corpus import stopwords
import string
import re
import spacy

# Scikit‑learn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import LabelEncoder
import torch

# Paths for persisted artifacts
DATA_PATH = os.path.join(os.path.dirname(__file__), "data.csv")
VECTORIZER_PATH = os.path.join(os.path.dirname(__file__), "models", "vectorizer.pkl")
LABEL_ENCODER_PATH = os.path.join(os.path.dirname(__file__), "models", "label_encoder.pkl")
MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "chatbot_model.pth")
BEST_MODEL_PATH = MODEL_PATH

# Ensure NLTK resources are available (download once if missing)
try:
    _ = stopwords.words("english")
except LookupError:
    nltk.download("stopwords")

# Load spaCy English model (download if not present)
try:
    _nlp = spacy.load("en_core_web_sm")
except OSError:
    # Download model programmatically
    from spacy.cli import download
    download("en_core_web_sm")
    _nlp = spacy.load("en_core_web_sm")


def load_dataset(csv_path: str = DATA_PATH) -> pd.DataFrame:
    """Read the CSV containing student support questions.

    Args:
        csv_path: Path to the CSV file.
    Returns:
        DataFrame with columns ``question`` and ``category``.
    """
    df = pd.read_csv(csv_path)
    # Basic sanity check
    if {"question", "category"}.issubset(df.columns) is False:
        raise ValueError("CSV must contain 'question' and 'category' columns")
    return df


def clean_text(text: str) -> str:
    """Perform comprehensive preprocessing:
    - Lower‑case
    - Remove punctuation
    - Collapse multiple spaces
    - Lemmatize tokens via spaCy
    - Remove English stopwords
    """
    # Lower‑case and strip
    text = text.lower().strip()
    # Remove punctuation
    text = text.translate(str.maketrans("", "", string.punctuation))
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)
    # spaCy tokenisation + lemmatization
    doc = _nlp(text)
    tokens = [token.lemma_ for token in doc if token.lemma_.strip()]
    # Remove stopwords
    stop_words = set(stopwords.words("english"))
    tokens = [t for t in tokens if t not in stop_words]
    return " ".join(tokens)

def preprocess_text(text: str) -> str:
    """Legacy wrapper kept for backward compatibility – forwards to ``clean_text``.
    """
    return clean_text(text)


def fit_vectorizer(texts: pd.Series, ngram_range: Tuple[int, int] = (1, 3), max_features: int = 10000, min_df: int = 1, max_df: float = 0.95) -> TfidfVectorizer:
    """Fit a TF‑IDF vectorizer with production‑grade defaults.

    Parameters
    ----------
    texts: pd.Series
        Pre‑processed text samples.
    ngram_range: tuple
        Include unigrams, bigrams and trigrams.
    max_features: int
        Upper bound on vocabulary size.
    min_df: int
        Minimum document frequency.
    max_df: float
        Maximum document frequency proportion.
    """
    vec = TfidfVectorizer(
        ngram_range=ngram_range,
        max_features=max_features,
        min_df=min_df,
        max_df=max_df,
        stop_words=None,  # stopwords already removed in ``clean_text``
        norm='l2',
        smooth_idf=True,
    )
    vec.fit(texts)
    joblib.dump(vec, VECTORIZER_PATH)
    return vec


def save_pickle(obj: Any, path: str) -> None:
    """Serialise ``obj`` to ``path`` using ``joblib``.
    Creates parent directories automatically.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    joblib.dump(obj, path)

def load_pickle(path: str) -> Any:
    """Load a pickled object from ``path``.
    Raises ``FileNotFoundError`` if missing.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Pickle file not found at {path}")
    return joblib.load(path)


def load_vectorizer() -> TfidfVectorizer:
    """Load the persisted TF‑IDF vectorizer using ``load_pickle``.
    """
    return load_pickle(VECTORIZER_PATH)


def fit_label_encoder(labels: pd.Series) -> LabelEncoder:
    """Fit a ``LabelEncoder`` for categorical targets and persist it.
    """
    le = LabelEncoder()
    le.fit(labels)
    save_pickle(le, LABEL_ENCODER_PATH)
    return le


def load_label_encoder() -> LabelEncoder:
    """Load the persisted label encoder using ``load_pickle``.
    """
    return load_pickle(LABEL_ENCODER_PATH)


def get_device() -> torch.device:
    """Return the best available torch device (GPU if available).
    """
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def save_model(model: torch.nn.Module, path: str = BEST_MODEL_PATH) -> None:
    """Save a PyTorch model's ``state_dict``.
    By default saves to ``BEST_MODEL_PATH`` (the checkpoint of the best validation loss).
    Ensures the destination directory exists.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    torch.save(model.state_dict(), path)


def load_model(model_class: Any, input_dim: int, num_classes: int, path: str = MODEL_PATH, device: torch.device = None) -> torch.nn.Module:
    """Instantiate ``model_class`` with the given dimensions and load weights.

    Parameters
    ----------
    model_class: Any
        The class of the model to instantiate (e.g., ChatbotModel).
    input_dim: int
        Dimensionality of the TF‑IDF input vectors.
    num_classes: int
        Number of output classes.
    path: str, optional
        Path to the saved ``state_dict``. Defaults to ``MODEL_PATH``.
    device: torch.device, optional
        Torch device for the model. If ``None`` the best available device is used.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Model file not found at {path}")
    device = device or get_device()
    # Instantiate the model with the required dimensions
    model = model_class(input_dim=input_dim, num_classes=num_classes)
    model.load_state_dict(torch.load(path, map_location=device))
    model.to(device)
    model.eval()
    return model
