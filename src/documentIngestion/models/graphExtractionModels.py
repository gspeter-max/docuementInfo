from pydantic import BaseModel, Field, field_validator


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
        from src.documentIngestion.graphRelationshipSchema import ALLOWED_RELATIONSHIP_TYPES

        if value not in ALLOWED_RELATIONSHIP_TYPES:
            raise ValueError(f"Unsupported relationship type: {value}")
        return value


class ChunkGraphExtractionResult(BaseModel):
    """This holds all the names and connections we found in one small piece of text."""

    entities: list[RawGraphEntity] = Field(default_factory=list)
    relationships: list[RawGraphRelationship] = Field(default_factory=list)
