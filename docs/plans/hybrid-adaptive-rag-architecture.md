# Hybrid Adaptive RAG Architecture

This document serves as a reference for the retrieval logic and mental model of the Hybrid Adaptive RAG system.

## 1. First-Principles Breakdown

1.  **Vector Search**: Retrieves data by **Similarity** (finds text chunks that look like the query).
2.  **Graph Search**: Retrieves data by **Connectivity** (traverses entities linked in Neo4j).
3.  **The Failure Point**: A query may have a high similarity score to a chunk that is factually incomplete or lacks relational context.
4.  **The Adaptive Logic**: Use the fastest retrieval method (Vector) first, verify the quality of the result (Grader), and escalate to the precise method (Graph) only if the first pass is insufficient.

## 2. Mental Model (Retrieval Flow)

```text
[ USER QUERY ]
      |
      v
[ ROUTER ] 
      |
      +----( A: Complex Intent )----> [ HYBRID SEARCH ] ----> [ ANSWER ]
      |                               (Vector + Graph)
      |
      +----( B: Simple Intent )-----> [ VECTOR SEARCH ]
                                             |
                                             v
                                      [ GRADER NODE ]
                                             |
                        +--------------------+--------------------+
                        |                                         |
                 ( Result: ENOUGH )                       ( Result: NOT ENOUGH )
                        |                                         |
                        v                                         v
                 [ GENERATE ANSWER ]                       [ EXTRACT ENTITIES ]
                                                                  |
                                                                  v
                                                           [ GRAPH TRAVERSAL ]
                                                                  |
                                                                  v
                                                           [ GENERATE ANSWER ]
```

### Breaking Points
*   **Router Failure**: Misclassifies a complex relationship query as a simple fact.
*   **Vector Failure**: Retrieves a text chunk with high semantic similarity that lacks the specific answer.
*   **Grader Failure**: Incorrectly verifies incomplete info, leading to a hallucination.

## 3. The Graph Agent (Relational Explorer)

The Graph Agent's job is to solve the "Scattered Data" problem by following physical connections in the database.

### Logic Step-by-Step
1.  **Identify Seeds**: Find starting nodes (entities) using either the Query or Vector Chunks.
2.  **Traverse (1-2 Hops)**: Pull all neighbors and relationships connected to those seeds.
3.  **Fact Assembly**: Convert the graph paths into a structured "Fact Sheet" for the LLM.

## 4. Why "Vector-First" is Better for Production

There are two ways to find starting points in the graph:

| Strategy | Logic | Advantage | Risk |
| :--- | :--- | :--- | :--- |
| **Direct Extraction** | Extract names from the Query only. | Extremely Fast. | Fails if the user uses a synonym or vague term. |
| **Vector-First** | Search Vector DB -> Extract entities from text. | **High Accuracy.** | Adds 1 extra LLM call for extraction. |

**Production Choice: Vector-First.**
It bridges the "Semantic Gap." If a user asks *"Who leads the AI team?"*, direct extraction finds nothing (no name). Vector search finds a chunk saying *"Artish Mahara leads the AI team,"* allowing the Graph Agent to then find everything connected to "Artish Mahara."

## 5. Intuitive Pseudo-code (Full Pipeline)

```python
def retrieve_information(user_query):
    # 1. Intent Routing
    intent = fast_llm_classify(user_query) # "simple" or "complex"

    # CASE 1: Query is complex - Go straight to Hybrid
    if intent == "complex":
        chunks = vector_database.search(user_query)
        entities = extract_entities(chunks)
        graph_facts = graph_agent.crawl_neo4j(entities)
        return generate_final_answer(chunks + graph_facts)

    # CASE 2: Query is simple - Use the Safety Net
    chunks = vector_database.search(user_query)
    
    # If the simple search actually worked, we are done (Fast Path)
    if llm_grader.is_sufficient(chunks, user_query):
        return generate_final_answer(chunks)
    
    # If simple search failed, escalate to Graph (Recovery Path)
    # We use the chunks we found as "clues" to find the right graph nodes
    entities = extract_entities(chunks)
    graph_facts = graph_agent.crawl_neo4j(entities)
    return generate_final_answer(chunks + graph_facts)
```

# reranker 
```python
import requests
from dotenv import load_dotenv
load_dotenv()

API_KEY = os.getenv("VOYAGE_API_KEY")

url = "https://api.voyageai.com/v1/embeddings"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

data = {
    "model": "voyage-3",
    "input": [
        "Machine learning is powerful",
        "I love building AI systems"
    ]
}

response = requests.post(url, headers=headers, json=data)

# Check response
print(response.status_code)

result = response.json()

# Extract embeddings
embeddings = [item["embedding"] for item in result["data"]]

print(len(embeddings))        # number of texts
print(len(embeddings[0]))     # embedding dimension
print(embeddings[0][:10])     # preview
``` 
