# syntax=docker/dockerfile:1
FROM python:3.11-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
COPY requirements.txt .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

FROM python:3.11-slim-bookworm AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp

WORKDIR /app
RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home app

COPY --from=builder /opt/venv /opt/venv
COPY main.py ./
COPY routes/ ./routes/
COPY utils/ ./utils/
COPY data/hadith/ ./data/hadith/
COPY data/quizes/ ./data/quizes/
COPY data/prayer_times/ ./data/prayer_times/
COPY THIRD_PARTY_NOTICES.md ./

USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/', timeout=3).close()"]

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
