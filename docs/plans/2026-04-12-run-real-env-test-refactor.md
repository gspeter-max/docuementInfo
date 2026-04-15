# Real Environment Test Refactor Implementation Plan

> **For Gemini:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

## Important Context For New Session Agent

**What we built today:** We just finished implementing the `Strict Graph Ingestion` plan (located at `docs/superpowers/plans/2026-04-12-strict-graph-ingestion.md`). The codebase now has a full pipeline that:
1. Reads a document and splits it into chunks.
2. Gets vector embeddings for each chunk.
3. Uses an AI (`extract_chunk_graph_data_in_parallel`) to find names (entities) and strict connections (relationships) from the text.
4. Uses code and AI (`resolve_entities_for_graph`) to clean up duplicate names.
5. Rewrites the old data to use the new clean names (`rewrite_graph_results_to_canonical_entities`).
6. Saves everything (chunks, embeddings, entities, mentions, and relationships) to a Neo4j database (`persist_document_graph`).

**The Goal of THIS Plan:** Currently, the manual test script (`tests/real_env_test/run_real_env_test.py`) just calls one big function (`ingest_document`) and finishes. We want to change the test script to run each step of document ingestion one by one. We will check if the data is correct after every step, and show us exactly what happens. At the end, we will save everything to a big text file called JSON so we can review the real output.

**Why are we doing this?** To achieve zero hallucination and clear visibility. We need to verify that each stage of the graph ingestion actually produces the expected data shape. By making the test script run step-by-step, we can add `assert` checks to stop if the data is empty or wrong.

**Architecture:** We stop calling the big function. We call the small functions one by one. After each small function, we check the data to make sure it is not empty and matches what we expect. We print a clear message for every check. We save all the checked data into a file.

**Tech Stack:** Python, asyncio, JSON.

---

### Task 1: Update the script to run steps one by one, verify data, and save a JSON report

**Files:**
- Modify: `tests/real_env_test/run_real_env_test.py`

**Step 1: Apply the exact code changes using a git diff**

We will change the file `tests/real_env_test/run_real_env_test.py`. We will remove the old code with the minus sign (`-`) and add the new code with the plus sign (`+`). 

Apply this exact git difference to the file.

```diff
--- tests/real_env_test/run_real_env_test.py
+++ tests/real_env_test/run_real_env_test.py
@@ -19,10 +19,16 @@
 import argparse
 import json
 from datetime import datetime, timezone
-from pathlib import Path
-from documentIngestion.ingestion import ingest_document
-from documentIngestion.models.ingestionModels import ingestionRequest
 import asyncio
+
+from config import mistral_api_key
+from documentIngestion.contextual_retrieval import build_contextualized_document, build_mistral_client
+from documentIngestion.ingestion import (
+    build_contextualized_chunk_embeddings,
+    extract_chunk_graph_data_in_parallel,
+    resolve_entities_for_graph,
+    persist_document_graph,
+)
+from documentIngestion.graphPersistence import rewrite_graph_results_to_canonical_entities
 
 
 
@@ -32,9 +38,81 @@
 # if _project_root not in sys.path:
 #     sys.path.insert(0, _project_root)
 
-from config import mistral_api_key
-from documentIngestion.contextual_retrieval import build_contextualized_document, build_mistral_client
 
+def convert_to_python_types(item):
+    """This turns objects we cannot save into normal text and lists so we can save them."""
+    if hasattr(item, "model_dump"):
+        return item.model_dump()
+    return str(item)
+
+
+async def run_pipeline_step_by_step(pdf_path: Path, output_dir: Path) -> None:
+    """We run each step one after the other. We check the data. We print a clear message."""
+    
+    log.info("Step 1: Read the document and split it into chunks")
+    client = await build_mistral_client()
+    document_data = await build_contextualized_document(file_path=str(pdf_path), client=client)
+    chunk_list = document_data["chunks"]
+    assert len(chunk_list) > 0, "Error: The document has zero chunks. The text reading failed."
+    log.info("Step 1 verified: The text is split into chunks successfully", number_of_chunks=len(chunk_list))
+
+    log.info("Step 2: Get numbers for each chunk to search them later")
+    embeddings_list = await build_contextualized_chunk_embeddings(chunk_list)
+    assert len(embeddings_list) == len(chunk_list), "Error: The number of number lists does not match the chunks."
+    log.info("Step 2 verified: All chunks have their numbers", number_of_embeddings=len(embeddings_list))
+
+    log.info("Step 3: Find names and connections in the text")
+    raw_graphs = await extract_chunk_graph_data_in_parallel(chunk_list)
+    assert len(raw_graphs) == len(chunk_list), "Error: The AI missed some chunks when finding names."
+    log.info("Step 3 verified: The AI looked at all chunks and returned data", number_of_results=len(raw_graphs))
+
+    log.info("Step 4: Clean up duplicate names")
+    resolution_result = await resolve_entities_for_graph(raw_graphs)
+    clean_names_map = resolution_result["canonical_name_by_raw_name"]
+    assert isinstance(clean_names_map, dict), "Error: We did not get a dictionary of clean names."
+    log.info("Step 4 verified: We have a map to clean the duplicate names", number_of_clean_names=len(clean_names_map))
+
+    log.info("Step 5: Change old names to clean names")
+    clean_graph = rewrite_graph_results_to_canonical_entities(raw_graphs, clean_names_map)
+    assert isinstance(clean_graph.entities, list), "Error: The clean entities must be a list."
+    assert isinstance(clean_graph.relationships, list), "Error: The clean relationships must be a list."
+    log.info("Step 5 verified: The names are clean and ready to save", 
+             total_clean_names=len(clean_graph.entities), 
+             total_connections=len(clean_graph.relationships))
+
+    log.info("Step 6: Save everything to the database")
+    try:
+        await persist_document_graph(document_data, embeddings_list, clean_graph)
+        log.info("Step 6 verified: Everything is saved to the database without errors")
+    except Exception as e:
+        log.error("Error: Saving to the database failed", error_message=str(e))
+        raise e
+
+    log.info("Step 7: Save all data to a text file on the computer")
+    time_now = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
+    file_name = f"{pdf_path.stem}_{time_now}.json"
+    full_path = output_dir / file_name
+    
+    all_data = {
+        "document_name": document_data["document_id"],
+        "total_chunks": len(chunk_list),
+        "chunks_data": chunk_list,
+        "found_names_and_connections": raw_graphs,
+        "clean_name_mapping": resolution_result,
+        "final_clean_data": clean_graph
+    }
+
+    try:
+        with open(full_path, "w", encoding="utf-8") as file_writer:
+            json.dump(all_data, file_writer, indent=2, default=convert_to_python_types)
+        log.info("Step 7 verified: We saved the final test report successfully", saved_file_path=str(full_path))
+    except Exception as e:
+        log.error("Error: We could not save the JSON file", error_message=str(e))
+        raise e
 
 def main() -> int:
     parser = argparse.ArgumentParser(description="Run a manual real-environment PDF smoke test.")
@@ -57,15 +135,9 @@
     if not mistral_api_key:
         raise EnvironmentError("MISTRAL_API_KEY is not configured in src.config")
 
-    ingestion_request = ingestionRequest(file_path=str(pdf_path))
-    log.info("Starting ingestion via run_real_env_test", pdf_path=str(pdf_path))
-    result = asyncio.run(ingest_document(ingestion_request))
-    log.info("Ingestion completed", result=str(result))
-
-    # print(f"Wrote report to: {output_path}")
-    # print(f"Chunks: {report['chunk_count']}")
-    # for chunk in report["chunks"]:
-    #     print(f"Chunk {chunk['chunk_index']}: {chunk['token_count']} tokens")
-    #     print(f"Context: {chunk['context']}")
+    log.info("We are starting the step by step test with checks", pdf_path=str(pdf_path))
+    asyncio.run(run_pipeline_step_by_step(pdf_path, output_dir))
+    log.info("The step by step test is completely done and passed all checks")
 
     return 0
```

**Step 2: Run the script to verify it works**

We will run the help command to see if the script has no syntax errors.
Run: `python tests/real_env_test/run_real_env_test.py --help`
Expected: PASS and print the help message.

**Step 3: Commit**

```bash
git add tests/real_env_test/run_real_env_test.py
git commit -m "test: add verification checks and step-by-step reporting to run_real_env_test script"
```
