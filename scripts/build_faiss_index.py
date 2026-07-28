"""Build the semantic-search FAISS index from the main FAQ dataset."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.semantic_search import (
    DATA_PATH,
    INDEX_PATH,
    METADATA_PATH,
    build_faiss_index,
    search_semantic,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or rebuild the FAISS index for semantic search")
    parser.add_argument("--data", type=str, default=str(DATA_PATH), help="Path to the source CSV file")
    parser.add_argument("--index", type=str, default=str(INDEX_PATH), help="Where to save the FAISS index")
    parser.add_argument("--metadata", type=str, default=str(METADATA_PATH), help="Where to save the metadata JSON")
    parser.add_argument("--query", type=str, default=None, help="Optional query to test after indexing")
    parser.add_argument("--top-k", type=int, default=5, help="Number of top matches to return for a test query")
    args = parser.parse_args()

    index, metadata = build_faiss_index(args.data, args.index, args.metadata)
    print(f"Built FAISS index with {index.ntotal} vectors")
    print(f"Saved metadata for {len(metadata)} rows to {args.metadata}")

    if args.query:
        print(f"\nTop results for query: {args.query}")
        for result in search_semantic(args.query, top_k=args.top_k, data_path=args.data, index_path=args.index, metadata_path=args.metadata, rebuild=False):
            print(f"- [{result['category']}] {result['question']} -> {result['answer']} (score={result['score']:.4f})")


if __name__ == "__main__":
    main()
