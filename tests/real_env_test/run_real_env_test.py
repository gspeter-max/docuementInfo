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
import asyncio

from config import mistral_api_key
from documentIngestion.contextual_retrieval import build_contextualized_document, build_mistral_client
from documentIngestion.ingestion import (
    build_contextualized_chunk_embeddings,
    extract_chunk_graph_data_in_parallel,
    resolve_entities_for_graph,
    persist_document_graph,
)
from documentIngestion.graphPersistence import rewrite_graph_results_to_canonical_entities



# Make the project root visible when this script is run directly.
# _project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# if _project_root not in sys.path:
#     sys.path.insert(0, _project_root)


def convert_to_python_types(item):
    """This turns objects we cannot save into normal text and lists so we can save them."""
    if hasattr(item, "model_dump"):
        return item.model_dump()
    return str(item)


async def run_pipeline_step_by_step(pdf_path: Path, output_dir: Path) -> None:
    """We run each step one after the other. We check the data. We print a clear message."""
    
    log.info("Step 1: Read the document and split it into chunks")
    client = await build_mistral_client()
    document_data = await build_contextualized_document(file_path=str(pdf_path), client=client)
    chunk_list = document_data["chunks"]
    assert len(chunk_list) > 0, "Error: The document has zero chunks. The text reading failed."
    log.info("Step 1 verified: The text is split into chunks successfully", number_of_chunks=len(chunk_list))

    log.info("Step 2: Get numbers for each chunk to search them later")
    embeddings_list = await build_contextualized_chunk_embeddings(chunk_list)
    assert len(embeddings_list) == len(chunk_list), "Error: The number of number lists does not match the chunks."
    log.info("Step 2 verified: All chunks have their numbers", number_of_embeddings=len(embeddings_list))

    log.info("Step 3: Find names and connections in the text")
    raw_graphs = await extract_chunk_graph_data_in_parallel(chunk_list)
    assert len(raw_graphs) == len(chunk_list), "Error: The AI missed some chunks when finding names."
    log.info("Step 3 verified: The AI looked at all chunks and returned data", number_of_results=len(raw_graphs))

    log.info("Step 4: Clean up duplicate names")
    resolution_result = await resolve_entities_for_graph(raw_graphs)
    clean_names_map = resolution_result["canonical_name_by_raw_name"]
    assert isinstance(clean_names_map, dict), "Error: We did not get a dictionary of clean names."
    log.info("Step 4 verified: We have a map to clean the duplicate names", number_of_clean_names=len(clean_names_map))

    log.info("Step 5: Change old names to clean names")
    clean_graph = rewrite_graph_results_to_canonical_entities(raw_graphs, clean_names_map)
    assert isinstance(clean_graph.entities, list), "Error: The clean entities must be a list."
    assert isinstance(clean_graph.relationships, list), "Error: The clean relationships must be a list."
    log.info("Step 5 verified: The names are clean and ready to save", 
             total_clean_names=len(clean_graph.entities), 
             total_connections=len(clean_graph.relationships))

    log.info("Step 6: Save everything to the database")
    try:
        await persist_document_graph(document_data, embeddings_list, clean_graph)
        log.info("Step 6 verified: Everything is saved to the database without errors")
    except Exception as e:
        log.error("Error: Saving to the database failed", error_message=str(e))
        raise e

    log.info("Step 7: Save all data to a text file on the computer")
    time_now = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    file_name = f"{pdf_path.stem}_{time_now}.json"
    full_path = output_dir / file_name
    
    all_data = {
        "document_name": document_data["document_id"],
        "total_chunks": len(chunk_list),
        "chunks_data": chunk_list,
        "found_names_and_connections": raw_graphs,
        "clean_name_mapping": resolution_result,
        "final_clean_data": clean_graph
    }

    try:
        with open(full_path, "w", encoding="utf-8") as file_writer:
            json.dump(all_data, file_writer, indent=2, default=convert_to_python_types)
        log.info("Step 7 verified: We saved the final test report successfully", saved_file_path=str(full_path))
    except Exception as e:
        log.error("Error: We could not save the JSON file", error_message=str(e))
        raise e

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

    log.info("We are starting the step by step test with checks", pdf_path=str(pdf_path))
    asyncio.run(run_pipeline_step_by_step(pdf_path, output_dir))
    log.info("The step by step test is completely done and passed all checks")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
