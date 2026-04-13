<p align="center">
  <img src="logo.png" alt="MiroWorld" width="160" />
</p>

<h1 align="center">MiroWorld</h1>

<p align="center">
  AI consulting simulator for policy, campaign, and product analysis
</p>

<p align="center">
  <a href="https://pebblepaw.github.io/MiroWorld/">
    <img src="https://img.shields.io/badge/GitHub%20Pages-Demo-0a66c2?logo=github" alt="GitHub Pages Demo" />
  </a>
  <a href="https://d3a03mb192176l.cloudfront.net/">
    <img src="https://img.shields.io/badge/AWS-Live%20App-ff9900?logo=amazonaws&logoColor=white" alt="AWS Live App" />
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/license-AGPL--3.0-blue.svg" alt="License: AGPL-3.0" />
  </a>
</p>

MiroWorld ingests source material into a knowledge graph, samples a synthetic population from the Nemotron Singapore personas dataset, runs a multi-round OASIS social simulation, then grounds report/chat/analytics on the resulting interactions and checkpoints.

Try the static demo on GitHub Pages or the live AWS deployment:

- GitHub Pages demo: [https://pebblepaw.github.io/MiroWorld/](https://pebblepaw.github.io/MiroWorld/)
- AWS live app: [https://d3a03mb192176l.cloudfront.net/](https://d3a03mb192176l.cloudfront.net/)

The hosted GitHub Pages demo is preloaded with a bundled Singapore public-policy scenario based on the 2026 Budget AI strategy source URL. Screen 1 opens with the source URL already filled, and the shipped cache reflects a 50-agent, 10-round run with four bundled analysis questions.

The repository ships:

- `backend/`: FastAPI API, simulation orchestration, SQLite-backed memory, LightRAG ingestion
- `frontend/`: React + Vite UI for Screen 0 through Screen 5
- `quick_start.sh`: local source-mode launcher
- `docker-compose.yml`: containerized demo/live stack with the OASIS sidecar

## Deployment Modes

Two local paths are supported for the open-source release:

- Source mode: run backend and frontend directly from this repository.
- Docker mode: run the production frontend, backend API, and OASIS sidecar via Docker Compose.

The root `.env.example` is the canonical environment template for both paths. `quick_start.sh` now auto-loads `.env` from the repo root, while Docker Compose reads the same file through `env_file`.

## Source Mode

### Prerequisites

- Python 3.11+ for the main backend virtualenv
- Python 3.11 specifically available on `PATH` for the OASIS sidecar (`python3.11`)
- Node.js 20+ and `npm`
- Optional: Ollama if you want free local live runs without external API keys

The main backend environment can be Python 3.11 or 3.12. The native OASIS runner still needs a separate Python 3.11 environment, and `quick_start.sh --mode live` will auto-create `backend/.venv311` if `python3.11` is installed.

### Setup

```bash
cp .env.example .env
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ./backend[dev]
cd frontend && npm install && cd ..
```

If you want to use countries whose Nemotron parquet files are not already present locally, set `HUGGINGFACE_API_KEY` in `.env`. The backend uses that key to download the selected country dataset on demand.

### Launch

Demo mode uses the bundled cached artifacts and is the fastest smoke test:

```bash
./quick_start.sh --mode demo
```

Live mode enables the native OASIS runtime:

```bash
./quick_start.sh --mode live
```

When live mode is enabled, the launcher will:

- read provider settings from `.env`
- validate or create `backend/.venv311`
- install pinned OASIS runtime dependencies into that sidecar if needed
- start the backend on `http://127.0.0.1:8000`
- start the frontend on `http://127.0.0.1:5173`

## Docker Mode

Docker Compose runs a production frontend build behind nginx, the FastAPI backend, and the Python 3.11 OASIS sidecar.

```bash
cp .env.example .env
docker compose up --build
```

Notes:

- `BOOT_MODE=demo` is the default and requires no provider key.
- For live Docker runs, the default `.env.example` is already oriented toward OpenRouter. Set `OPENROUTER_API_KEY` and switch `BOOT_MODE=live`.
- If you want Docker to use a host Ollama daemon instead, set `LLM_PROVIDER="ollama"` and `LLM_BASE_URL="http://host.docker.internal:11434/v1/"` in `.env`.
- The backend healthcheck also verifies that the OASIS sidecar is reachable.

## LLM Provider Setup

### Ollama

Use this for the cheapest source-mode live setup.

1. Install Ollama and start the local daemon.
2. Pull the required models:

```bash
ollama pull qwen3:4b-instruct-2507-q4_K_M
ollama pull nomic-embed-text
```

3. Set the provider block in `.env`:

```bash
LLM_PROVIDER="ollama"
LLM_MODEL="qwen3:4b-instruct-2507-q4_K_M"
LLM_EMBED_MODEL="nomic-embed-text"
LLM_BASE_URL="http://127.0.0.1:11434/v1/"
```

For Docker, replace the base URL with `http://host.docker.internal:11434/v1/`.

### OpenRouter

Use this for the simplest live Docker setup and a cheap hosted-compatible path.

1. Create an OpenRouter account and generate an API key.
2. Set:

```bash
LLM_PROVIDER="openrouter"
LLM_MODEL="meta-llama/llama-3.1-8b-instruct:free"
LLM_EMBED_MODEL="openai/text-embedding-3-small"
LLM_BASE_URL="https://openrouter.ai/api/v1/"
OPENROUTER_API_KEY="your-key"
```

### Gemini

1. Create a Google AI Studio key.
2. Set:

```bash
LLM_PROVIDER="google"
LLM_MODEL="gemini-2.5-flash-lite"
LLM_EMBED_MODEL="gemini-embedding-001"
LLM_BASE_URL="https://generativelanguage.googleapis.com/v1beta/openai/"
LLM_API_KEY="your-key"
```

`GEMINI_API_KEY` is also supported for compatibility with older local setups.

### OpenAI

1. Create an OpenAI API key.
2. Set:

```bash
LLM_PROVIDER="openai"
LLM_MODEL="gpt-5-mini"
LLM_EMBED_MODEL="text-embedding-3-small"
LLM_BASE_URL="https://api.openai.com/v1/"
OPENAI_API_KEY="your-key"
```

## Boot Modes

- `demo`: local backend/frontend with cached demo data available as a fallback
- `live`: native OASIS simulation with real provider calls
- `demo-static`: frontend-only GitHub Pages build using bundled `frontend/public/demo-output.json`

The GitHub Pages build uses `VITE_BOOT_MODE=demo-static` and `VITE_PUBLIC_BASE=/MiroWorld/`.

## Development

Backend:

```bash
cd backend
python -m pip install -e .[dev]
python -m ruff check src
python -m pytest -q tests
```

Frontend:

```bash
cd frontend
npm ci
npm run lint
npm run test -- --run
npm run build
```

Docker smoke test:

```bash
cp .env.example .env
docker compose up --build -d
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:5173/
docker compose down -v
```

## License

This project is licensed under the AGPL-3.0 license. See [LICENSE](LICENSE).
