FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install ".[dev]"

COPY src/ ./src/
COPY tests/ ./tests/

ENV PYTHONPATH=/app/src

CMD ["python", "-m", "sandbox_init.server"]
