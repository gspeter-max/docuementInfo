from pathlib import Path
import os

from dotenv import load_dotenv

_project_root = Path(__file__).resolve().parents[1]
load_dotenv(_project_root / ".env")

llama_parse_api_key = os.environ.get("LLAMA_PARSE_APIKEY", "").strip()
jina_api_key = os.environ.get("JINA_API_KEY", "").strip()
mistral_api_key = os.environ.get("MISTRAL_API_KEY", "").strip()

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
