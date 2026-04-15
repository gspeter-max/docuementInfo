from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root))

import src  # This triggers structlog.configure in src/__init__.py
import structlog

from config import mistral_api_key
from documentIngestion.contextual_retrieval import build_contextualized_document, build_mistral_client
from documentIngestion.ingestion import (
    build_contextualized_chunk_embeddings,
    extract_chunk_graph_data_in_parallel,
    resolve_entities_for_graph,
    persist_document_graph,
)
from documentIngestion.graphPersistence import rewrite_graph_results_to_canonical_entities

log = structlog.get_logger(__name__)


def convert_to_python_types(item):
    """This turns objects we cannot save into normal text and lists so we can save them."""
    if hasattr(item, "model_dump"):
        return item.model_dump()
    return str(item)


def write_report(report_path: Path, payload: dict[str, object]) -> Path:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, indent=2, default=convert_to_python_types), encoding="utf-8")
    return report_path


def build_report_payload(
    *,
    status: str,
    failed_stage: str,
    error_message: str,
    document_id: str,
    chunk_count: int,
    relationship_count: int,
    output_path: Path,
) -> dict[str, object]:
    return {
        "status": status,
        "failed_stage": failed_stage,
        "error_message": error_message,
        "document_id": document_id,
        "chunk_count": chunk_count,
        "relationship_count": relationship_count,
        "output_path": str(output_path),
    }


async def run_pipeline_step_by_step(pdf_path: Path, output_dir: Path) -> Path:
    """Run the smoke pipeline step by step and always write a compact report."""
    status = "success"
    failed_stage = ""
    error_message = ""
    document_id = ""
    chunk_count = 0
    relationship_count = 0
    report_path = output_dir / f"{pdf_path.stem}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    current_stage = "startup"

    try:
        current_stage = "document_chunking"
        log.info("Starting document chunking")
        client = await build_mistral_client()
        document_data = await build_contextualized_document(file_path=str(pdf_path), client=client)
        document_id = document_data["document_id"]
        chunk_list = document_data["chunks"]
        chunk_count = len(chunk_list)
        assert len(chunk_list) > 0, "Error: The document has zero chunks. The text reading failed."
        log.info("Document chunking complete", number_of_chunks=len(chunk_list))

        current_stage = "embedding"
        log.info("Starting embeddings")
        embeddings_list = await build_contextualized_chunk_embeddings(chunk_list)
        assert len(embeddings_list) == len(chunk_list), "Error: The number of number lists does not match the chunks."
        log.info("Embeddings complete", number_of_embeddings=len(embeddings_list))

        current_stage = "graph_extraction"
        log.info("Starting graph extraction")
        raw_graphs = await extract_chunk_graph_data_in_parallel(chunk_list)
        assert len(raw_graphs) == len(chunk_list), "Error: The AI missed some chunks when finding names."
        relationship_count = sum(len(chunk_graph.relationships) for chunk_graph in raw_graphs)
        log.info("Graph extraction complete", number_of_results=len(raw_graphs))

        current_stage = "entity_resolution"
        log.info("Starting entity resolution")
        resolution_result = await resolve_entities_for_graph(raw_graphs)
        clean_names_map = resolution_result["canonical_name_by_raw_name"]
        assert isinstance(clean_names_map, dict), "Error: We did not get a dictionary of clean names."
        log.info("Entity resolution complete", number_of_clean_names=len(clean_names_map))

        current_stage = "graph_persistence"
        log.info("Starting graph persistence")
        clean_graph = rewrite_graph_results_to_canonical_entities(raw_graphs, clean_names_map)
        assert isinstance(clean_graph.entities, list), "Error: The clean entities must be a list."
        assert isinstance(clean_graph.relationships, list), "Error: The clean relationships must be a list."
        relationship_count = len(clean_graph.relationships)
        await persist_document_graph(document_data, embeddings_list, clean_graph)
        log.info("Graph persistence complete")
    except Exception as exc:
        status = "error"
        failed_stage = current_stage
        error_message = str(exc)
        log.error("Smoke test stage failed", stage=current_stage, error_message=error_message)

    report_payload = build_report_payload(
        status=status,
        failed_stage=failed_stage,
        error_message=error_message,
        document_id=document_id,
        chunk_count=chunk_count,
        relationship_count=relationship_count,
        output_path=report_path,
    )
    report_path = write_report(report_path, report_payload)
    log.info("Wrote smoke test report", report_path=str(report_path), status=status)
    return report_path

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
    report_path = asyncio.run(run_pipeline_step_by_step(pdf_path, output_dir))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report["status"] != "success":
        log.error("The step by step test finished with an error", report_path=str(report_path), failed_stage=report["failed_stage"])
        return 1
    log.info("The step by step test is completely done and passed all checks", report_path=str(report_path))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
