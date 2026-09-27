# Продакшен / инференс: CPU-only (публикация в GHCR и docker compose).

FROM python:3.11-slim-bookworm

ENV PIP_NO_CACHE_DIR=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV TORCHINDUCTOR_CACHE_DIR=/tmp/torch-inductor-cache

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --root-user-action=ignore --upgrade pip setuptools wheel

COPY requirements-docker.txt .
RUN pip install --root-user-action=ignore -r requirements-docker.txt

COPY app/ ./app/
COPY config.yaml .
COPY pytest.ini .
COPY tests/ ./tests/
COPY ci/ ./ci/

RUN mkdir -p model

EXPOSE 5000

CMD ["python", "-m", "app.main", "--host", "0.0.0.0", "--port", "5000"]
