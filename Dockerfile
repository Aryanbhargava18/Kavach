# One always-on container: Kavach keeps the simulated world in memory and streams live updates (SSE),
# so it needs a long-running server (Railway, Render, Fly, any VM), not serverless functions.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV KAVACH_PLANNER=offline KAVACH_PACE=0.35 PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
