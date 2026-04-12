import requests
import json 
import asyncio 
import structlog

log = structlog.get_logger(__name__)

class embeddingModel:
    def __init__(self, 
        api_key: str, 
        base_url : str = "https://api.jina.ai/v1/embeddings", 
        embeddingModel : str = "jina-embeddings-v2-base-en",
        max_concurrency : int = 10
    ):
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        self.embedModel = embeddingModel
        self.url = base_url
        self.max_concurrency = max_concurrency
        
    async def generateEmebedding(self, text: str) -> list[float]:
        sem = asyncio.Semaphore(self.max_concurrency)
        async with sem:
            data = {
                "model" : self.embedModel,
                "task" : "retrieval.query",
                "input" : [
                    text 
                ]
            }

            response = requests.post(self.url, headers=self.headers, data = json.dumps(data))
            if response.status_code != 200:
                log.error("Jina API error", status_code=response.status_code, response_text=response.text)
                raise Exception(f"Error generating embedding: {response.status_code}")
            
            return response.json()["data"][0]["embedding"]

    async def generate_embeddings_for_text_list(self, texts: list[str]) -> list[list[float]]:
        """This turns a list of words into a list of numbers all at once. These numbers help us understand what the words mean so we can find similar words later."""
        data = {
            "model": self.embedModel,
            "task": "retrieval.query",
            "input": texts,
        }
        response = requests.post(self.url, headers=self.headers, data=json.dumps(data))
        response.raise_for_status()
        response_payload = response.json()
        return [row["embedding"] for row in response_payload["data"]]