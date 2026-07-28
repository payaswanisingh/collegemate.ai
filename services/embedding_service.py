"""Utilities for generating semantic embeddings for the knowledge base."""

from __future__ import annotations

import os
from typing import Iterable, List, Optional, Sequence

import numpy as np
from sentence_transformers import SentenceTransformer

try:
    import torch
except ImportError:  # pragma: no cover - torch is expected in this project
    torch = None


MODEL_NAME = "BAAI/bge-small-en-v1.5"
DEFAULT_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "models",
    "embeddings",
)

_MODEL: Optional[SentenceTransformer] = None


def get_embedding_model(model_name: str = MODEL_NAME, cache_dir: Optional[str] = None) -> SentenceTransformer:
    """Load and cache the embedding model once per process."""
    global _MODEL
    if _MODEL is not None:
        return _MODEL

    resolved_cache_dir = cache_dir or DEFAULT_CACHE_DIR
    os.makedirs(resolved_cache_dir, exist_ok=True)

    device = "cuda" if torch is not None and torch.cuda.is_available() else "cpu"
    _MODEL = SentenceTransformer(model_name, cache_folder=resolved_cache_dir, device=device)
    return _MODEL


def encode_texts(texts: Sequence[str], normalize: bool = True) -> np.ndarray:
    """Return dense embeddings for a sequence of text values as float32 arrays."""
    if not texts:
        return np.empty((0, 0), dtype=np.float32)

    model = get_embedding_model()
    embeddings = model.encode(
        list(texts),
        normalize_embeddings=normalize,
        convert_to_numpy=True,
        show_progress_bar=False,
        batch_size=32,
    )
    return np.asarray(embeddings, dtype=np.float32)


def encode_text(text: str, normalize: bool = True) -> np.ndarray:
    """Encode a single text string and return its embedding vector."""
    return encode_texts([text], normalize=normalize)[0]
