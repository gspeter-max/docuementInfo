from typing import Any

from documentIngestion.models.graphExtractionModels import ChunkGraphExtractionResult, CanonicalGraphPersistencePayload


def rewrite_graph_results_to_canonical_entities(
    raw_chunk_graph_results: list[ChunkGraphExtractionResult],
    canonical_name_by_raw_name: dict[str, str],
) -> CanonicalGraphPersistencePayload:
    """This function takes all the names we found and changes them to the single best name we chose for them, so we can save them correctly."""
    rewritten_entities = []
    rewritten_relationships = []
    for chunk_graph_result in raw_chunk_graph_results:
        for entity in chunk_graph_result.entities:
            rewritten_entities.append({
                "canonical_name": canonical_name_by_raw_name.get(entity.entity_name, entity.entity_name),
                "entity_type": entity.entity_type,
                "chunk_id": entity.chunk_id,
                "evidence_text": entity.evidence_text,
            })
        for relationship in chunk_graph_result.relationships:
            rewritten_relationships.append({
                "source_entity_name": canonical_name_by_raw_name.get(relationship.source_entity_name, relationship.source_entity_name),
                "relationship_type": relationship.relationship_type,
                "target_entity_name": canonical_name_by_raw_name.get(relationship.target_entity_name, relationship.target_entity_name),
                "chunk_id": relationship.chunk_id,
                "evidence_text": relationship.evidence_text,
            })
    return CanonicalGraphPersistencePayload(entities=rewritten_entities, relationships=rewritten_relationships)


def merge_duplicate_relationship_payloads(
    relationship_payloads: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """This function takes many identical connections and squishes them into one, making sure we remember all the places we found them."""
    merged_relationships_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for relationship_payload in relationship_payloads:
        relationship_key = (
            relationship_payload["source_entity_name"],
            relationship_payload["relationship_type"],
            relationship_payload["target_entity_name"],
        )
        merged_relationships_by_key.setdefault(relationship_key, relationship_payload)
    return list(merged_relationships_by_key.values())


def build_neo4j_graph_write_payload(
    document_id: str,
    canonical_entities: list[dict[str, Any]],
    rewritten_relationships: list[dict[str, Any]],
) -> dict[str, Any]:
    """This function packages up all the deduplicated entities, their mentions, and deduplicated relationships for saving."""
    unique_entities = {}
    mentions = []
    
    for entity in canonical_entities:
        canonical_name = entity["canonical_name"]
        if canonical_name not in unique_entities:
            unique_entities[canonical_name] = {
                "canonical_name": canonical_name,
                "entity_type": entity["entity_type"]
            }
        
        mentions.append({
            "canonical_name": canonical_name,
            "document_id": document_id,
            "chunk_id": entity["chunk_id"],
            "evidence_text": entity["evidence_text"],
        })
        
    for rel in rewritten_relationships:
        rel["document_id"] = document_id
        
    merged_relationships = merge_duplicate_relationship_payloads(rewritten_relationships)

    return {
        "document_id": document_id,
        "entities": list(unique_entities.values()),
        "mentions": mentions,
        "relationships": merged_relationships,
    }
