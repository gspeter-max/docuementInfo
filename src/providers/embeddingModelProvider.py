import requests
import json 
import asyncio 

class embeddingModel:
    def __init__(self, 
        api_key: str, 
        base_url : str = "https://api.jina.ai/v1/embeddings", 
        embeddingModel : str = "jina-embeddings-v2-small-en",
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
                "normalized" : True,
                "input" : [
                    text 
                ]
            }

            response = requests.post(self.url, headers=self.headers, data = json.dumps(data))
            if response.status_code != 200:
                raise Exception(f"Error generating embedding: {response.status_code}")
            
            return response.json()["data"][0]["embedding"]