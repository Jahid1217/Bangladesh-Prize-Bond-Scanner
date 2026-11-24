# --- Frontend build -------------------------------------------------------
FROM node:22-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# --- Runtime --------------------------------------------------------------
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PBS_DB_PATH=/data/database/prize_bonds.db \
    PBS_EXPORTS_DIR=/data/exports \
    PBS_CAPTURES_DIR=/data/database/captures \
    PBS_TESSERACT_CMD=/usr/bin/tesseract

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-eng tesseract-ocr-ben \
        libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt
COPY backend/ backend/
COPY scripts/ scripts/
COPY --from=frontend /build/frontend/dist frontend/dist

RUN mkdir -p /data/database /data/exports
EXPOSE 8000
CMD ["python", "backend/run.py", "--host", "0.0.0.0", "--port", "8000"]
