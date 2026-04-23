"""
Application entry point.

Creates the FastAPI app and registers all routers.
Run with: uvicorn app.main:app --reload
"""
from fastapi import FastAPI
import uvicorn

from app.ingestionAPI import ingestionRouter
from app.retrieveAPI import retrieveRouter

app = FastAPI(
    title="Hybrid Adaptive RAG API",
    description="Document ingestion and intelligent retrieval using Vector + Graph search.",
    version="1.0.0",
)

app.include_router(ingestionRouter)
app.include_router(retrieveRouter)


def main():
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
