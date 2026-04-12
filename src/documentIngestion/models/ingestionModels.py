from pydantic import BaseModel


class ingestionRequest(BaseModel):
    file_path: str

class ingestionResponse(BaseModel):
    status: str
    message: str
    raw_entity_count: int = 0
    canonical_entity_count: int = 0
    relationship_count: int = 0