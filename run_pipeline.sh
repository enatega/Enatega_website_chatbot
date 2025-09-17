#!/usr/bin/env bash
set -euo pipefail

echo "1) Scrape"
python web_scraping.py

echo "2) Rewrite (overwrite files)"
python rewrite_texts.py

echo "3) Chunk (writes chunks_all.*)"
python chunking.py

echo "4) Ingest to Qdrant Cloud"
python ingest_qdrant.py --recreate

echo "5) Ensure Qdrant payload indexes"
python ensure_indexes.py

echo "Done."
