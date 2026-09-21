"""CLI entrypoint for ingestion. Usage: python3 -m scripts.run_ingest"""

from app.rag.ingest import run_ingestion

if __name__ == "__main__":
    run_ingestion()