# Neo4j — Local Docker Setup

Runs Neo4j 5 community edition locally using Docker Compose.
No cloud account needed. All data persists in `neo4j/data/`.

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running

---

## Setup (one-time)

1. **Set your credentials** in the project root `.env`:

   ```
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=your_strong_password_here
   ```

   See `.env.example` for a full template.

2. **Start Neo4j**:

   ```bash
   cd dockerHostedServices
   docker compose up -d
   ```

3. **Wait ~15 seconds** for Neo4j to initialise, then open the browser UI:
   ```
   http://localhost:7474
   ```
   Log in with your `NEO4J_USER` / `NEO4J_PASSWORD`.

---

## Daily usage

```bash
# Start
docker compose up -d

# Stop (data is preserved)
docker compose down

# View logs
docker compose logs -f neo4j

# Full reset — deletes ALL graph data
docker compose down -v
rm -rf neo4j/data neo4j/logs
```

---

## Running the real-env smoke test

```bash
cd ..   # back to project root
PYTHONPATH=. python3 tests/real_env_test/run_real_env_test.py --pdf data/pankajkumar.pdf
```

---

## Ports

| Port | What |
|---|---|
| `7474` | Neo4j Browser UI |
| `7687` | Bolt (Python app connects here) |

---

## Data persistence

All graph data lives in `dockerHostedServices/neo4j/data/`.
This folder is git-ignored — it is never committed.
