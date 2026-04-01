from pathlib import Path
import os

from dotenv import load_dotenv

_project_root = Path(__file__).resolve().parents[1]
load_dotenv(_project_root / ".env")

llama_parse_api_key = os.environ.get("LLAMA_PARSE_APIKEY", "").strip()

if not llama_parse_api_key:
    raise EnvironmentError(
        "LLAMA_PARSE_APIKEY environment variable is not set. "
        "Please set it in your .env file or as an environment variable."
    )

lightning_api_key = (
    os.environ.get("LIGHTNING_API_KEY", "")
    or os.environ.get("LIGHTNING_AI_API_KEY", "")
).strip()
lightning_ai_api_key = lightning_api_key
