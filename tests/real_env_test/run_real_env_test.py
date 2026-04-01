"""
Manual real-environment smoke test runner.

Usage:
    uv run python tests/real_env_test/run_real_env_test.py --pdf data/sample.pdf

This script parses a real PDF, chunks the extracted text, and writes a JSON
report to tests/real_env_test/real_env_test_results/.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Make the project root visible when this script is run directly.
# _project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# if _project_root not in sys.path:
#     sys.path.insert(0, _project_root)

from src.config import lightning_api_key
from src.documentIngestion.contextual_retrieval import build_contextualized_document, build_lightning_client


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

    if not lightning_api_key:
        raise EnvironmentError("LIGHTNING_API_KEY is not configured in src.config")

    client = build_lightning_client(api_key=lightning_api_key)
    report = build_contextualized_document(
        file_path=str(pdf_path),
        client=client,
    )
    report["created_at"] = datetime.now(timezone.utc).isoformat()
    report["input_pdf"] = str(pdf_path)

    output_path = output_dir / f"{pdf_path.stem}_contextualized.json"
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")

    # print(f"Wrote report to: {output_path}")
    # print(f"Chunks: {report['chunk_count']}")
    # for chunk in report["chunks"]:
    #     print(f"Chunk {chunk['chunk_index']}: {chunk['token_count']} tokens")
    #     print(f"Context: {chunk['context']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
