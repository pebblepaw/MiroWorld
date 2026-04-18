FROM python:3.11-slim

WORKDIR /app/backend

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=src
ENV OASIS_PYTHON_BIN=/usr/local/bin/python

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml backend/README.md ./
COPY backend/requirements-oasis-runtime.txt ./
COPY backend/Sample_Inputs ./Sample_Inputs
COPY backend/src ./src
COPY backend/scripts ./scripts
COPY backend/data ./data
COPY config /app/config

RUN python - <<'PY'
from pathlib import Path

source = Path("requirements-oasis-runtime.txt")
target = Path("requirements-oasis-runtime-hosted.txt")
lines = [line for line in source.read_text(encoding="utf-8").splitlines() if not line.startswith("torch==")]
target.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu torch==2.10.0+cpu
RUN pip install --no-cache-dir -r requirements-oasis-runtime-hosted.txt
RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["uvicorn", "miroworld.main:app", "--host", "0.0.0.0", "--port", "8000"]
