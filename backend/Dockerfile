FROM python:3.12-slim

WORKDIR /app/backend

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=src

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml backend/README.md ./
COPY backend/Sample_Inputs ./Sample_Inputs
COPY backend/src ./src
COPY backend/scripts ./scripts
COPY backend/data ./data
COPY config /app/config

RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["uvicorn", "miroworld.main:app", "--host", "0.0.0.0", "--port", "8000"]
