# McKAInsey

McKAInsey is an AI consulting simulator for policy and campaign analysis. The application pairs a synthetic persona dataset with a multi-step workflow for knowledge ingestion, sampling, simulation, report review, and analytics.

The repository currently contains:

- a FastAPI backend under `backend/`
- a React + Vite frontend under `frontend/`
- a local launcher in `quick_start.sh`
- a Docker Compose stack in `docker-compose.yml`

## What Runs Locally

Two local entry points are supported at a high level:

- Source mode: run the backend and frontend directly from the repository.
- Docker mode: run the stack through Docker Compose.

The repo root `.env.example` documents the environment variables used by the launcher, backend, and frontend. Keep your real `.env` file untracked.

## Quick Start

1. Copy the example environment file.

```bash
cp .env.example .env
```

2. Start the local app.

```bash
./quick_start.sh --mode demo
```

3. Open the UI shown by the launcher.

`--mode live` is available for the native OASIS runtime path when the required Python 3.11 sidecar and model provider credentials are configured.

## Docker Mode

Docker Compose is included for the containerized stack. Use it when you want the app services to run in containers rather than directly on your machine.

```bash
docker compose up --build
```

Refer to `docker-compose.yml` for the current service layout and exposed ports.

## Environment

The root `.env.example` is the best starting point for local development.

Common values include:

- launcher ports and host bindings
- `VITE_API_BASE` and `VITE_BOOT_MODE`
- LLM provider selection and base URLs
- optional provider API keys
- local data and cache paths
- OASIS runtime paths and limits

## Development

Backend:

```bash
cd backend
python -m pip install -e .[dev]
python -m pytest -q
```

Frontend:

```bash
cd frontend
npm install
npm run test -- --run
npm run build
```

## License

This project is licensed under the AGPL-3.0 license. See [LICENSE](LICENSE).
