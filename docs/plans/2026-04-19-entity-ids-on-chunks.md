# Entity IDs on Chunks Implementation Plan (Simple Version)

> **For Gemini:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Store a list of short "nicknames" (entity IDs) on every piece of text (Chunk) in our database. This helps the computer find important names and their connections very quickly.

**Architecture:** We take a name, clean it up, and turn it into a short 12-character code. We then tell every piece of text which codes are hidden inside it and save that list in Neo4j.

**Tech Stack:** Python, Neo4j (Cypher), hashlib (SHA-256).

---

### Task 1: Add a "Name-to-Code" Generator

**Files:**
- Modify: `src/documentIngestion/graphPersistence.py`

**Step 1: Write a simple test to check our generator**
Create `tests/documentIngestion/test_id_generation.py`:
```python
import hashlib
from src.documentIngestion.graphPersistence import generate_stable_entity_id

def test_generate_stable_entity_id_is_consistent():
    """This test checks if the same name always gets the same code."""
    name = "Artish Mahara"
    id1 = generate_stable_entity_id(name)
    id2 = generate_stable_entity_id(name)
    assert id1 == id2
    assert len(id1) == 12

def test_generate_stable_entity_id_ignores_case_and_space():
    """This test checks if extra spaces or big letters don't confuse the code maker."""
    name1 = "  Artish Mahara  "
    name2 = "artish mahara"
    assert generate_stable_entity_id(name1) == generate_stable_entity_id(name2)
```

**Step 2: Run test to verify it fails**
Run: `pytest tests/documentIngestion/test_id_generation.py`
Expected: FAIL (The computer doesn't know what 'generate_stable_entity_id' is yet.)

**Step 3: Implement the name-to-code function**
In `src/documentIngestion/graphPersistence.py`:
```python
import hashlib

def generate_stable_entity_id(name: str) -> str:
    """
    This function takes a name (like 'Apple') and turns it into a short 
    12-character code (like 'a1b2c3'). 
    
    It's like giving every important thing a unique ID card so the 
    computer doesn't get confused between different things with the 
    same name.
    """
    # 1. Clean up the name (remove extra spaces and make letters small)
    normalized_name = " ".join(name.lower().strip().split())
    
    # 2. Turn the name into a scrambled secret code (a hash)
    secret_code = hashlib.sha256(normalized_name.encode()).hexdigest()
    
    # 3. Take just the first 12 letters of that code to keep it short
    short_code = secret_code[:12]
    
    return short_code
```

**Step 4: Run test to verify it passes**
Run: `pytest tests/documentIngestion/test_id_generation.py`
Expected: PASS

**Step 5: Commit**
```bash
git add src/documentIngestion/graphPersistence.py tests/documentIngestion/test_id_generation.py
git commit -m "feat: add a simple tool to turn names into unique codes"
```

---

### Task 2: Update the Database to Remember Codes

**Files:**
- Modify: `src/db/neo4j/cypherQuerys.py`

**Step 1: Update the save_chunk function**
In `src/db/neo4j/cypherQuerys.py`:
```python
async def save_chunk(
    client: Neo4jClient,
    chunk: dict[str, Any],
    embedding: list[float],
    entity_ids: list[str] = None, # This is our new list of codes
) -> None:
    """
    This function saves a small piece of a document into our database.
    Now, it also saves a list of codes (entity_ids) for the important 
    names found in this piece of text.
    """
    query = """
    MERGE (c:Chunk {chunk_id: $chunk_id})
    SET c.text        = $text,
        c.context     = $context,
        c.document_id = $document_id,
        c.embedding   = $embedding,
        c.entity_ids  = $entity_ids  // We added this line to save the codes!
    """
    await client.execute_query(query, {
        "chunk_id":    chunk["chunk_id"],
        "text":        chunk["text"],
        "context":     chunk["context"],
        "document_id": chunk["document_id"],
        "embedding":   embedding,
        "entity_ids":  entity_ids or [], # If there are no codes, save an empty list
    })
```

**Step 2: Commit**
```bash
git add src/db/neo4j/cypherQuerys.py
git commit -m "feat: teach the database to remember entity codes on text chunks"
```

---

### Task 3: Match the Codes to the Right Text

**Files:**
- Modify: `src/documentIngestion/graphPersistence.py`

**Step 1: Update the payload builder**
In `src/documentIngestion/graphPersistence.py`:
```python
def build_neo4j_graph_write_payload(
    document_id: str,
    canonical_entities: list[dict[str, Any]],
    rewritten_relationships: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    This function gathers all the names and connections we found in a 
    document and prepares them to be saved.
    
    We updated it to also map each piece of text (Chunk) to the unique 
    entity_id of the names found inside it.
    """
    unique_entities = {}
    mentions = []
    # This dictionary will map: piece_of_text -> [list of name entity_ids]
    chunk_to_entity_ids = {}

    for entity in canonical_entities:
        clean_name = entity["canonical_name"]
        # Use our tool from Task 1 to get the code
        entity_id = generate_stable_entity_id(clean_name)

        if clean_name not in unique_entities:
            unique_entities[clean_name] = {
                "canonical_name": clean_name,
                "entity_type": entity["entity_type"],
                "entity_id": entity_id # Remember the code for the entity
            }

        mentions.append({
            "canonical_name": clean_name,
            "entity_id": entity_id,
            "document_id": document_id,
            "chunk_id": entity["chunk_id"],
            "evidence_text": entity["evidence_text"],
        })
        
        # Link this code to the specific piece of text it came from
        parent_chunk_id = entity["chunk_id"]
        if parent_chunk_id not in chunk_to_entity_ids:
            chunk_to_entity_ids[parent_chunk_id] = set()
        chunk_to_entity_ids[parent_chunk_id].add(entity_id)

    # Convert sets to lists so the database can read them easily
    chunk_to_entity_ids = {k: list(v) for k, v in chunk_to_entity_ids.items()}

    # ... (the rest of the function for relationships stays the same)
    merged_relationships = merge_duplicate_relationship_payloads(rewritten_relationships)

    return {
        "document_id": document_id,
        "entities": list(unique_entities.values()),
        "mentions": mentions,
        "relationships": merged_relationships,
        "chunk_to_entity_ids": chunk_to_entity_ids # Pass our new mapping along
    }
```

**Step 2: Commit**
```bash
git add src/documentIngestion/graphPersistence.py
git commit -m "feat: match name codes to their original text chunks in the payload"
```

---

### Task 4: Connect Everything in the Main Pipeline

**Files:**
- Modify: `src/documentIngestion/ingestion.py`

**Step 1: Update persist_document_graph**
In `src/documentIngestion/ingestion.py`:
```python
async def persist_document_graph(
    contextualized_document: dict[str, Any],
    contextualized_chunk_embeddings: list[list[float]],
    canonical_graph_payload: Any,
    graph_write_payload: dict[str, Any] # We pass the whole payload now
) -> None:
    """
    This is the function that actually talks to the database and 
    saves everything. We updated it to send the name codes to each 
    piece of text.
    """
    neo4j_client = Neo4jClient(neo4j_uri, neo4j_user, neo4j_password)
    try:
        await create_vector_index(neo4j_client, _INDEX_NAME, _EMBEDDING_DIM)
        await save_document_node(...)

        chunks = contextualized_document["chunks"]
        # Get our map of text-to-codes
        chunk_to_ids_map = graph_write_payload.get("chunk_to_entity_ids", {})

        # Save all chunks at once, each with its own list of name codes
        await asyncio.gather(*[
            save_chunk(
                neo4j_client, 
                chunk, 
                embedding, 
                entity_ids=chunk_to_ids_map.get(chunk["chunk_id"], [])
            )
            for chunk, embedding in zip(chunks, contextualized_chunk_embeddings)
        ])
        
        # Save the graph nodes and connections
        await save_entity_nodes_and_relationships(neo4j_client, graph_write_payload)
    finally:
        await neo4j_client.close()
```

**Step 2: Update the main ingestion call**
In `src/documentIngestion/ingestion.py`, update `ingest_document_graph`:
```python
    # ... after cleaning up the names
    graph_write_payload = build_neo4j_graph_write_payload(
        contextualized_document["document_id"],
        canonical_graph_payload.entities,
        canonical_graph_payload.relationships,
    )
    
    # Send the finished payload to be saved
    await persist_document_graph(
        contextualized_document, 
        contextualized_chunk_embeddings, 
        canonical_graph_payload,
        graph_write_payload
    )
```

**Step 3: Commit**
```bash
git add src/documentIngestion/ingestion.py
git commit -m "feat: update the main ingestion pipeline to include name codes"
```

---

### Task 5: Check if it Really Works!

**Step 1: Run the big test**
Run: `pytest tests/documentIngestion/test_ingestion_pipeline.py`
Expected: PASS (This ensures the whole document still processes correctly.)

**Step 2: Peek inside the database**
Run this command in the Neo4j Browser to see the result:
`MATCH (c:Chunk) WHERE c.entity_ids IS NOT NULL RETURN c.chunk_id, c.entity_ids LIMIT 5`
Expected: You should see a list of short codes for every chunk!
