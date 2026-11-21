# ---- stage 1: build the React frontend --------------------------------------
FROM node:20-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- stage 2: API + CV pipeline + built frontend -----------------------------
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
# CPU-only PyTorch keeps the image small. For GPU use an NVIDIA CUDA base image / remove this line.
RUN pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu \
 && pip install -r backend/requirements.txt
COPY backend/ backend/
COPY scripts/ scripts/
COPY sample_data/ sample_data/
COPY --from=web /web/dist frontend/dist
ARG DOWNLOAD_WEIGHTS=true
ARG YOLO_MODEL=yolo11n.pt
RUN if [ "$DOWNLOAD_WEIGHTS" = "true" ]; then python scripts/download_weights.py "$YOLO_MODEL" || true; fi
WORKDIR /app/backend
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
