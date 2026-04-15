from pydantic import BaseModel, Field, field_validator
from typing import Any
from src.__init__ import log 

class RawGraphEntity(BaseModel):
    """This tells us about one name or thing we found in a small piece of text, before we check if we already found it before."""

    entity_name: str = Field(min_length=1)
    entity_type: str = Field(min_length=1)
    chunk_id: str = Field(min_length=1)
    evidence_text: str = Field(min_length=1)


class RawGraphRelationship(BaseModel):
    """This shows how two names or things are connected to each other in a piece of text, using only the connections we allow."""

    source_entity_name: str = Field(min_length=1)
    relationship_type: str = Field(min_length=1)
    target_entity_name: str = Field(min_length=1)
    evidence_text: str = Field(min_length=1)
    chunk_id: str = Field(min_length=1)

    @field_validator("relationship_type")
    @classmethod
    def validate_relationship_type(cls, value: str) -> str:
        from documentIngestion.graphRelationshipSchema import ALLOWED_RELATIONSHIP_TYPES

        if value not in ALLOWED_RELATIONSHIP_TYPES:
            log.warning(f"Unsupported relationship type: {value} \n {value } -- changed to -> RELATED_TO" )
            value = "RELATED_TO"
        return value


class ChunkGraphExtractionResult(BaseModel):
    """This holds all the names and connections we found in one small piece of text."""

    entities: list[RawGraphEntity] = Field(default_factory=list)
    relationships: list[RawGraphRelationship] = Field(default_factory=list)


class AmbiguousEntityPairForResolution(BaseModel):
    """This holds two names that look a bit similar but we are not completely sure if they are the same thing, so we need to ask the AI to decide."""

    left_name: str
    right_name: str
    similarity_score: float


class EntityResolutionDecision(BaseModel):
    """This is the final answer from the AI about whether two names mean the same thing, and what the best name to use for both of them is."""

    left_name: str
    right_name: str
    should_merge: bool
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)


class CanonicalGraphPersistencePayload(BaseModel):
    """Holds rewritten canonical entities and relationships before saving."""
    
    entities: list[dict[str, Any]]
    relationships: list[dict[str, Any]]
    mentions: list[dict[str, Any]] = Field(default_factory=list)
    document_id: str = ""
