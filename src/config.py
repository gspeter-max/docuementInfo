from pathlib import Path
import os

from dotenv import load_dotenv

_project_root = Path(__file__).resolve().parents[1]
load_dotenv(_project_root / ".env", override=True)

llama_parse_api_key = os.environ.get("LLAMA_PARSE_APIKEY", "").strip()
jina_api_key = os.environ.get("JINA_API_KEY", "").strip()
mistral_api_key = os.environ.get("MISTRAL_API_KEY", "").strip()
voyage_api_key = os.environ.get("VOYAGE_API_KEY", "").strip()

neo4j_uri = os.environ.get("NEO4J_URI", "neo4j://localhost:7687").strip()
neo4j_user = os.environ.get("NEO4J_USER", "808a94e8").strip()
neo4j_password = os.environ.get("NEO4J_PASSWORD", "").strip()

if not llama_parse_api_key:
    raise EnvironmentError(
        "LLAMA_PARSE_APIKEY environment variable is not set. "
        "Please set it in your .env file or as an environment variable."
    )

if not jina_api_key:
    raise EnvironmentError(
        "JINA_API_KEY environment variable is not set. "
        "Please set it in your .env file or as an environment variable."
    )
