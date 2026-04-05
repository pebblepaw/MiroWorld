# Infrastructure: Docker Setup

> **Implements**: Phase Q (Q6, Q7)
> **UserInput Refs**: A1

## Overview

The entire stack runs via `docker compose up`. Four services: frontend (Vite/React), backend (FastAPI), FalkorDB (graph DB for Graphiti), and OASIS sidecar (Python 3.11 simulation engine).

## docker-compose.yml

```yaml
version: "3.9"

services:
  # ── Frontend ──────────────────────────────────────
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "5173:5173"
    environment:
      - VITE_API_URL=http://backend:8000
    depends_on:
      - backend
    volumes:
      - ./frontend/src:/app/src  # Hot reload in dev
    networks:
      - mckainsey

  # ── Backend ───────────────────────────────────────
  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile
    ports:
      - "8000:8000"
    environment:
      - FALKORDB_HOST=falkordb
      - FALKORDB_PORT=6379
      - OASIS_SIDECAR_HOST=oasis-sidecar
      - OASIS_SIDECAR_PORT=8001
      - CONFIG_DIR=/app/config
      - DATA_DIR=/app/data
    env_file:
      - .env  # User API keys (GEMINI_API_KEY, OPENAI_API_KEY, etc.)
    depends_on:
      falkordb:
        condition: service_healthy
    volumes:
      - ./config:/app/config:ro
      - ./data:/app/data
      - ./backend:/app/backend
    networks:
      - mckainsey

  # ── FalkorDB (Graphiti graph store) ───────────────
  falkordb:
    image: falkordb/falkordb:latest
    ports:
      - "6379:6379"
    volumes:
      - falkordb_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
    networks:
      - mckainsey

  # ── OASIS Sidecar (Python 3.11) ──────────────────
  oasis-sidecar:
    build:
      context: .
      dockerfile: backend/Dockerfile.oasis
    ports:
      - "8001:8001"
    environment:
      - DATA_DIR=/app/data
    volumes:
      - ./data:/app/data
      - ./backend/scripts:/app/scripts:ro
    networks:
      - mckainsey

networks:
  mckainsey:
    driver: bridge

volumes:
  falkordb_data:
```

## Dockerfiles

### Frontend Dockerfile

```dockerfile
# frontend/Dockerfile
FROM node:20-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Dev target (used in docker-compose)
FROM node:20-alpine AS dev
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
```

### Backend Dockerfile

```dockerfile
# backend/Dockerfile
FROM python:3.12-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY backend/pyproject.toml backend/requirements*.txt ./backend/
RUN pip install --no-cache-dir -e ./backend[graphiti]

# Copy source
COPY backend/ ./backend/
COPY config/ ./config/

EXPOSE 8000
CMD ["uvicorn", "backend.src.mckainsey.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

### OASIS Sidecar Dockerfile

```dockerfile
# backend/Dockerfile.oasis
FROM python:3.11-slim

# OASIS requires Python 3.11
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements-oasis-runtime.txt ./
RUN pip install --no-cache-dir -r requirements-oasis-runtime.txt

COPY backend/scripts/ ./scripts/

EXPOSE 8001
CMD ["python", "-m", "scripts.oasis_server", "--port", "8001"]
```

## Environment Variables (`.env`)

```bash
# .env (user-provided)
GEMINI_API_KEY=your-key-here
OPENAI_API_KEY=your-key-here        # optional
ZEP_API_KEY=your-key-here           # optional, fallback only
DEFAULT_PROVIDER=gemini
DEFAULT_MODEL=gemini-2.0-flash
```

## Networking

All services on the `mckainsey` bridge network:
- Frontend → Backend: `http://backend:8000` (container name resolution)
- Backend → FalkorDB: `bolt://falkordb:6379`
- Backend → OASIS: `http://oasis-sidecar:8001`
- Host → Frontend: `http://localhost:5173`
- Host → Backend: `http://localhost:8000`

**Latency**: <1ms between containers (localhost-equivalent). LLM API calls are the bottleneck (100-2000ms).

## Startup

```bash
# First time (pulls images, builds containers)
docker compose up --build

# Subsequent runs
docker compose up

# Development (with hot reload for frontend)
docker compose up frontend backend falkordb
# OASIS sidecar only needed for live simulations
```

## Graceful Degradation (B2)

The backend MUST NOT exit if Ollama is not installed. Provider availability is checked lazily:
- At session creation: User selects provider
- At simulation start: Backend verifies the provider is reachable
- If unreachable: Return 503 with descriptive error, not a crash

```python
# Instead of:
if not check_ollama():
    sys.exit(1)  # ← REMOVE THIS

# Do:
async def verify_provider(session_config):
    provider = session_config["provider"]
    if provider == "ollama":
        if not await ping_ollama():
            raise HTTPException(503, "Ollama is not running. Start Ollama or select a different provider.")
    elif provider == "gemini":
        if not session_config.get("api_key"):
            raise HTTPException(400, "Gemini API key is required.")
```

## Tests

- [ ] `docker compose up` starts all 4 services without errors
- [ ] Frontend accessible at `http://localhost:5173`
- [ ] Backend responds to `GET /health` at `http://localhost:8000`
- [ ] FalkorDB responds to `redis-cli ping` inside container
- [ ] Backend can connect to FalkorDB on port 6379
- [ ] `.env` API keys are accessible in backend container
- [ ] `docker compose down` stops all services cleanly
- [ ] Volume persists FalkorDB data across restarts
