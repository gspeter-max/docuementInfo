# Input Data
Chunk id: {chunk_id}
Chunk text:
{chunk_text}

---
# Example Output Format (One-Shot)
If the chunk id was "doc1::0" and the text was "Alice engineers software using Python at Neo4j.", and assuming "USES" and "WORKS_AT" are allowed types, your output should look like this:
{{
  "entities": [
    {{
      "entity_name": "Alice",
      "entity_type": "Person",
      "chunk_id": "doc1::0",
      "evidence_text": "Alice engineers software using Python at Neo4j."
    }},
    {{
      "entity_name": "Python",
      "entity_type": "Technology",
      "chunk_id": "doc1::0",
      "evidence_text": "Alice engineers software using Python at Neo4j."
    }},
    {{
      "entity_name": "Neo4j",
      "entity_type": "Organization",
      "chunk_id": "doc1::0",
      "evidence_text": "Alice engineers software using Python at Neo4j."
    }}
  ],
  "relationships": [
    {{
      "source_entity_name": "Alice",
      "relationship_type": "USES",
      "target_entity_name": "Python",
      "evidence_text": "engineers software using Python",
      "chunk_id": "doc1::0"
    }},
    {{
      "source_entity_name": "Alice",
      "relationship_type": "WORKS_AT",
      "target_entity_name": "Neo4j",
      "evidence_text": "at Neo4j",
      "chunk_id": "doc1::0"
    }}
  ]
}}
---

Process the Input Data above and return ONLY the JSON object. Do not include markdown code blocks or explanations.
