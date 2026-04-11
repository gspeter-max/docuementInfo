from pydantic import BaseModel


class ingestionRequest(BaseModel):
    file_path: str

class ingestionResponse(BaseModel):
    status: str
    message: str