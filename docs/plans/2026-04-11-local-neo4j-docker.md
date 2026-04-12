# Local Neo4j Docker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` or `superpowers:subagent-driven-development` to implement this plan step by step.

**Goal:** Run Neo4j in Docker on this computer and update the project so it connects to the local Neo4j server instead of the cloud Neo4j server.

**Result:** After this work, the project should be able to use `neo4j://localhost:7687` with local credentials, and Neo4j should run from a Docker container started from this repository.

---

## 1. Project Structure and File Responsibility

Use clear file locations and keep each file focused on one job.

- `docker-compose.yml`
  Purpose: Start the local Neo4j Docker container for this repository.
- `.env`
  Purpose: Store the connection values used by the project at runtime.
- `src/config.py`
  Purpose: Load environment values and provide Neo4j connection settings to the application.
- `data/neo4j/data/`
  Purpose: Store Neo4j database files on the local machine so data stays after container restart.

**Why `docker-compose.yml` should stay in the repository root:**
- Docker Compose normally looks for this file in the root.
- It is easier to run with `docker compose up -d`.
- The file name is standard and easy to understand.

---

## 2. Current Codebase Facts

These facts are already true in this repository:

- `src/config.py` already loads `.env` from the project root.
- `src/documentIngestion/ingestion.py` already reads `neo4j_uri`, `neo4j_user`, and `neo4j_password` from `src/config.py`.
- Neo4j client code already exists in `src/db/neo4j/__init__.py`.
- The repository already has a `data/` directory, so storing Neo4j data under `data/neo4j/data/` fits the current structure.

---

## 3. Planned Changes

### Task 1: Add Docker Compose File for Local Neo4j

**Files:**
- Create: `docker-compose.yml`

**Purpose:** Add one clear Docker entry point for starting local Neo4j.

- [ ] Create `docker-compose.yml` in the repository root.
- [ ] Use the Neo4j Docker image.
- [ ] Expose port `7474` for Neo4j Browser.
- [ ] Expose port `7687` for the Python application.
- [ ] Set local authentication with `NEO4J_AUTH`.
- [ ] Mount `./data/neo4j/data:/data` so database files stay on disk.

**Exact git difference:**

```diff
--- /dev/null
+++ b/docker-compose.yml
@@ -0,0 +1,13 @@
services:
  neo4j:
    image: neo4j:5.15
    container_name: local-neo4j
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      NEO4J_AUTH: neo4j/password
      NEO4J_PLUGINS: '["apoc"]'
    volumes:
      - ./data/neo4j/data:/data
```

**Why this name is clear:**
- Service name `neo4j` matches the database.
- Container name `local-neo4j` clearly shows this is the local instance.

---

### Task 2: Update Environment Values in `.env`

**Files:**
- Modify: `.env`

**Purpose:** Make runtime configuration point to the local Neo4j container.

- [ ] Replace the cloud Neo4j URI with the local URI.
- [ ] Keep the username as `neo4j`.
- [ ] Replace the cloud password with the local Docker password.

**Exact git difference:**

```diff
--- a/.env
+++ b/.env
@@ -6,3 +6,3 @@
-NEO4J_USER=neo4j
-NEO4J_PASSWORD=URZkdD-eTFnQB-VAvHQHTebE2bFQYPctqrGD8JqT0YY
-NEO4J_URI=neo4j+s://808a94e8.databases.neo4j.io
+NEO4J_USER=neo4j
+NEO4J_PASSWORD=password
+NEO4J_URI=neo4j://localhost:7687
```

**Important note:**
- This change replaces the current cloud connection values in `.env`.
- If cloud access is still needed later, keep a backup before changing this file.

---

### Task 3: Update Neo4j Defaults in `src/config.py`

**Files:**
- Modify: `src/config.py`

**Purpose:** Make the fallback values in code match the local Docker setup.

**Current situation:**
- `neo4j_uri` already defaults to `neo4j://localhost:7687`
- `neo4j_user` still defaults to the old cloud username
- `neo4j_password` has no local fallback value

- [ ] Keep the local fallback URI.
- [ ] Change the fallback user to `neo4j`.
- [ ] Change the fallback password to `password`.

**Exact git difference:**

```diff
--- a/src/config.py
+++ b/src/config.py
@@ -10,6 +10,6 @@
 
 neo4j_uri = os.environ.get("NEO4J_URI", "neo4j://localhost:7687").strip()
-neo4j_user = os.environ.get("NEO4J_USER", "808a94e8").strip()
-neo4j_password = os.environ.get("NEO4J_PASSWORD", "").strip()
+neo4j_user = os.environ.get("NEO4J_USER", "neo4j").strip()
+neo4j_password = os.environ.get("NEO4J_PASSWORD", "password").strip()
 
 if not llama_parse_api_key:
```

**Why this change is needed:**
- It keeps the code consistent with `.env`.
- It avoids mixing local Docker values with old cloud defaults.

---

### Task 4: Start Local Neo4j and Verify It

**Files:**
- Use: `docker-compose.yml`
- Use: `.env`
- Use: `src/config.py`

**Purpose:** Confirm the local Neo4j setup works from this repository.

- [ ] Start the Neo4j container.
- [ ] Confirm Docker created the local Neo4j container.
- [ ] Confirm the application config now points to the local Neo4j server.
- [ ] Run one project check that depends on the configured environment.

**Commands:**

```bash
docker compose up -d
docker compose ps
```

**Expected result:**
- The `local-neo4j` container is running.
- Ports `7474` and `7687` are mapped.

**Check the application configuration:**

```bash
sed -n '1,80p' src/config.py
rg -n '^NEO4J_(URI|USER|PASSWORD)=' .env
```

**Expected result:**
- `src/config.py` shows local fallback values.
- `.env` shows local Neo4j connection values.

**Optional project verification:**

```bash
pytest tests/documentIngestion/contextual_retrieval/test_contextual_retrieval_integration.py
```

**Important note about this test:**
- This test file is not a direct Neo4j integration test.
- It is only a basic project check after the configuration update.
- If you want a true Neo4j verification later, add a dedicated Neo4j connection test.

---

## 4. Final Output Checklist

The work is complete only if all items below are true:

- [ ] `docker-compose.yml` exists in the repository root.
- [ ] `.env` points to `neo4j://localhost:7687`.
- [ ] `src/config.py` uses local Neo4j fallback values.
- [ ] `docker compose up -d` starts Neo4j successfully.
- [ ] Neo4j data is stored under `data/neo4j/data/`.

---

## 5. Suggested Next Improvement

This is not required for the first version, but it would make the setup better:

- Add a dedicated test file such as `tests/db/neo4j/test_local_neo4j_connection.py`
  Purpose: Verify that the application can open a real connection to the local Neo4j container.
