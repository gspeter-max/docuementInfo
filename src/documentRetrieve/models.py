"""
Pydantic models for the retrieval and query endpoints.
"""
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str = Field(..., description="The user query to be answered.")
    top_k: int = Field(5, description="Number of vector chunks to retrieve initially.")
    top_k_rerank: int = Field(3, description="Number of chunks to keep after reranking.")


class QueryResponse(BaseModel):
    answer: str = Field(..., description="The generated answer to the user's query.")
    intent: str = Field(..., description="The classified intent ('simple' or 'complex').")
    escalated_to_graph: bool = Field(..., description="True if graph traversal was used.")
    escalation_reason: str = Field("", description="The reason for graph escalation, if any.")
    context_used: list[str] = Field(..., description="The final reranked text chunks used for context.")
