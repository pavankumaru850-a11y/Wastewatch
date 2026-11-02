# WasteWatch API. Build:  docker build -t wastewatch-api ./backend
# The backend requirements include the runtime for the bundled classifier.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY requirements.txt .
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
 && pip install -r requirements.txt \
 && rm -rf /var/lib/apt/lists/*

COPY app ./app
COPY config ./config
# a trained model (backend/models/best.pt) is baked into the image so a hosted server has it; docker-compose can still mount over it
COPY models ./models
# uploads + models live on volumes; the app never runs as root
RUN useradd --create-home --uid 10001 app \
 && mkdir -p /data/uploads /app/models \
 && chown -R app:app /data /app
USER app

ENV APP_ENV=production UPLOAD_DIR=/data/uploads
EXPOSE 8000
# PORT is set by the host (Render sets it); defaults to 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"

# One worker: the login rate limiter and geocoder cache are per-process. Scale with a reverse proxy if needed.
CMD ["sh", "-c", "python -m app.bootstrap && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers"]
