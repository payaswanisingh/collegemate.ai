"""Semantic retrieval helpers built on FAISS and sentence embeddings."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import faiss
import numpy as np
import pandas as pd

from services.embedding_service import encode_texts


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data.csv"
VECTOR_DB_DIR = PROJECT_ROOT / "vector_db"
INDEX_PATH = VECTOR_DB_DIR / "index.faiss"
METADATA_PATH = VECTOR_DB_DIR / "metadata.json"
RELEVANCE_THRESHOLD = 0.8
CAMPUS_TOPIC_TERMS = {
    "fee", "fees", "tuition", "admission", "exam", "examination", "scholarship", "hostel",
    "library", "campus", "student", "course", "department", "faculty", "placement",
    "attendance", "certificate", "document", "registration", "alumni", "sports", "semester",
    "result", "finance", "portal", "calendar", "lab", "class", "academic"
}

_INDEX_CACHE: Optional[faiss.Index] = None
_METADATA_CACHE: Optional[List[Dict[str, Any]]] = None
_CACHE_KEY: Optional[Tuple[str, str, str]] = None


def _build_search_text(row: Dict[str, Any]) -> str:
    """Create the embedding text from question and category only."""
    parts = [str(row.get("question", "")).strip(), str(row.get("category", "")).strip()]
    return " | ".join(part for part in parts if part)


def _normalize_text(text: Any) -> str:
    """Normalize text for lightweight token matching."""
    return re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).strip()


def _looks_like_campus_query(query: str) -> bool:
    """Heuristically detect whether the query appears to be about campus FAQ content."""
    tokens = set(_normalize_text(query).split())
    return bool(tokens & CAMPUS_TOPIC_TERMS)


def _is_relevant_result(query: str, result: Dict[str, Any]) -> bool:
    """Filter out weak or unrelated semantic matches before sending context to Gemini."""
    score = float(result.get("score", 0.0) or 0.0)
    if score < RELEVANCE_THRESHOLD:
        return False

    if not _looks_like_campus_query(query):
        return False

    candidate_text = " ".join(
        [str(result.get("question", "") or ""), str(result.get("category", "") or "")]
    )
    query_tokens = set(_normalize_text(query).split())
    candidate_tokens = set(_normalize_text(candidate_text).split())
    if not query_tokens or not candidate_tokens:
        return False

    overlap = len(query_tokens & candidate_tokens) / max(1, len(query_tokens | candidate_tokens))
    return overlap >= 0.08


def load_dataset(data_path: Optional[Path | str] = None) -> pd.DataFrame:
    """Load the FAQ dataset from CSV and validate the required columns."""
    path = Path(data_path or DATA_PATH)
    df = pd.read_csv(path)
    required_columns = {"question", "category", "answer"}
    missing_columns = required_columns.difference(df.columns)
    if missing_columns:
        raise ValueError(f"Dataset is missing required columns: {sorted(missing_columns)}")
    return df


def build_faiss_index(
    data_path: Optional[Path | str] = None,
    index_path: Optional[Path | str] = None,
    metadata_path: Optional[Path | str] = None,
) -> Tuple[faiss.Index, List[Dict[str, Any]]]:
    """Build a FAISS index from the FAQ dataset and save metadata separately."""
    dataset = load_dataset(data_path)
    resolved_index_path = Path(index_path or INDEX_PATH)
    resolved_metadata_path = Path(metadata_path or METADATA_PATH)

    texts = [_build_search_text(row) for _, row in dataset.iterrows()]
    embeddings = encode_texts(texts)
    if embeddings.ndim != 2:
        raise ValueError("Embeddings must be a 2D array")

    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)
    index.add(embeddings.astype(np.float32))

    metadata = []
    for row_index, row in dataset.iterrows():
        metadata.append(
            {
                "row_index": int(row_index),
                "question": str(row.get("question", "")).strip(),
                "category": str(row.get("category", "")).strip(),
                "answer": str(row.get("answer", "")).strip(),
                "search_text": _build_search_text(row),
            }
        )

    resolved_index_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_metadata_path.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(resolved_index_path))
    with open(resolved_metadata_path, "w", encoding="utf-8") as handle:
        json.dump(metadata, handle, ensure_ascii=False, indent=2)

    global _INDEX_CACHE, _METADATA_CACHE, _CACHE_KEY
    _INDEX_CACHE = index
    _METADATA_CACHE = metadata
    _CACHE_KEY = (
        str(Path(data_path or DATA_PATH).resolve()),
        str(resolved_index_path.resolve()),
        str(resolved_metadata_path.resolve()),
    )

    return index, metadata


def load_faiss_index(
    index_path: Optional[Path | str] = None,
    metadata_path: Optional[Path | str] = None,
) -> Tuple[faiss.Index, List[Dict[str, Any]]]:
    """Load a previously built FAISS index and its metadata from disk."""
    resolved_index_path = Path(index_path or INDEX_PATH)
    resolved_metadata_path = Path(metadata_path or METADATA_PATH)

    if not resolved_index_path.exists():
        raise FileNotFoundError(f"FAISS index not found at {resolved_index_path}")
    if not resolved_metadata_path.exists():
        raise FileNotFoundError(f"Metadata file not found at {resolved_metadata_path}")

    index = faiss.read_index(str(resolved_index_path))
    with open(resolved_metadata_path, "r", encoding="utf-8") as handle:
        metadata = json.load(handle)
    return index, metadata


def ensure_index(
    data_path: Optional[Path | str] = None,
    index_path: Optional[Path | str] = None,
    metadata_path: Optional[Path | str] = None,
    rebuild: bool = False,
) -> Tuple[faiss.Index, List[Dict[str, Any]]]:
    """Build the index if missing, or load it when already present."""
    global _INDEX_CACHE, _METADATA_CACHE, _CACHE_KEY

    resolved_index_path = Path(index_path or INDEX_PATH)
    resolved_metadata_path = Path(metadata_path or METADATA_PATH)
    cache_key = (
        str(Path(data_path or DATA_PATH).resolve()),
        str(resolved_index_path.resolve()),
        str(resolved_metadata_path.resolve()),
    )

    if not rebuild and _INDEX_CACHE is not None and _METADATA_CACHE is not None and _CACHE_KEY == cache_key:
        return _INDEX_CACHE, _METADATA_CACHE

    if rebuild or not resolved_index_path.exists() or not resolved_metadata_path.exists():
        return build_faiss_index(data_path=data_path, index_path=resolved_index_path, metadata_path=resolved_metadata_path)

    index, metadata = load_faiss_index(index_path=resolved_index_path, metadata_path=resolved_metadata_path)
    _INDEX_CACHE = index
    _METADATA_CACHE = metadata
    _CACHE_KEY = cache_key
    return index, metadata


def search_semantic(
    query: str,
    top_k: int = 5,
    data_path: Optional[Path | str] = None,
    index_path: Optional[Path | str] = None,
    metadata_path: Optional[Path | str] = None,
    rebuild: bool = False,
) -> List[Dict[str, Any]]:
    """Return the top matching FAQ rows for a user query using semantic search."""
    if not query or not query.strip():
        return []

    index, metadata = ensure_index(data_path=data_path, index_path=index_path, metadata_path=metadata_path, rebuild=rebuild)
    if not metadata:
        return []

    query_vector = encode_texts([query.strip()]).astype(np.float32)
    effective_top_k = min(max(1, top_k), len(metadata))
    distances, indices = index.search(query_vector, effective_top_k)

    results: List[Dict[str, Any]] = []
    for distance, match_index in zip(distances[0], indices[0]):
        if match_index < 0:
            continue
        item = metadata[int(match_index)]
        results.append(
            {
                "score": float(distance),
                "question": item.get("question"),
                "category": item.get("category"),
                "answer": item.get("answer"),
                "row_index": item.get("row_index"),
            }
        )

    relevant_results = [result for result in results if _is_relevant_result(query, result)]
    return relevant_results[:effective_top_k]
