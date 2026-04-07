FROM python:3.12-slim

WORKDIR /app/backend

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml backend/README.md ./
COPY backend/src ./src
COPY backend/scripts ./scripts

RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["uvicorn", "mckainsey.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
