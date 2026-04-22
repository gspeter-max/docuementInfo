from fastapi import FastAPI
import uvicorn

from src.documentIngestion.ingestion import ingestionRouter
from src.documentRetrieve.retrieve import retrieveRouter

app = FastAPI(title="Hybrid Adaptive RAG API")

app.include_router(ingestionRouter)
app.include_router(retrieveRouter)

def main():
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    main()
