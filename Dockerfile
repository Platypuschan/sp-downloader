FROM python:3.13-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
LABEL org.opencontainers.image.source="https://github.com/Platypuschan/sp-downloader"
LABEL org.opencontainers.image.description="South Park downloader with atomic publication of completed episodes"
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY downloader.py .
ENV PYTHONUNBUFFERED=1 DOWNLOAD_DIR=/data/downloads WORK_DIR=/data/work
VOLUME ["/data"]
ENTRYPOINT ["python", "/app/downloader.py"]
