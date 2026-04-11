from db.neo4j import Neo4jClient
from typing import Any

async def  create_vector_index(client: Neo4jClient, index_name: str, dimension: int):
    query = f"""
    CREATE VECTOR INDEX {index_name} IF NOT EXISTS FOR (n:Chunk)
    ON (n.embedding)
    OPTIONS {{
        indexConfig: {{
            type: 'hnsw',
            efConstruction: 64,
            maxConnections: 32
        }},
        vectorStoreConfig: {{
            dimension: {dimension}
        }}
    }}
    """
    await client.execute_query(query)


async def save_chunk(client: Neo4jClient, chunk: dict[str, Any]):
    