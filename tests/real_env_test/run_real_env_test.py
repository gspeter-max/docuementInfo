"""
Manual real-environment smoke test runner.

Usage:
    uv run python tests/real_env_test/run_real_env_test.py --pdf data/sample.pdf

This script parses a real PDF, chunks the extracted text, and writes a JSON
report to tests/real_env_test/real_env_test_results/.
"""
from __future__ import annotations
import sys
from pathlib import Path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root))

import src  # This triggers structlog.configure in src/__init__.py
import structlog

log = structlog.get_logger(__name__)

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from documentIngestion.ingestion import ingest_document
from documentIngestion.models.ingestionModels import ingestionRequest
import asyncio



# Make the project root visible when this script is run directly.
# _project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# if _project_root not in sys.path:
#     sys.path.insert(0, _project_root)

from config import mistral_api_key
from documentIngestion.contextual_retrieval import build_contextualized_document, build_mistral_client


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a manual real-environment PDF smoke test.")
    parser.add_argument("--pdf", required=True, help="Path to the PDF to parse and chunk.")
    parser.add_argument(
        "--output-dir",
        default="tests/real_env_test/real_env_test_results",
        help="Directory where the JSON report will be written.",
    )
    args = parser.parse_args()

    pdf_path = Path(args.pdf).expanduser().resolve()
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if not mistral_api_key:
        raise EnvironmentError("MISTRAL_API_KEY is not configured in src.config")

    ingestion_request = ingestionRequest(file_path=str(pdf_path))
    log.info("Starting ingestion via run_real_env_test", pdf_path=str(pdf_path))
    result = asyncio.run(ingest_document(ingestion_request))
    log.info("Ingestion completed", result=str(result))

    # print(f"Wrote report to: {output_path}")
    # print(f"Chunks: {report['chunk_count']}")
    # for chunk in report["chunks"]:
    #     print(f"Chunk {chunk['chunk_index']}: {chunk['token_count']} tokens")
    #     print(f"Context: {chunk['context']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
