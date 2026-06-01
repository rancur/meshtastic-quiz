FROM python:3.12-slim

WORKDIR /app

# Install deps first for layer caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# App
COPY meshquiz ./meshquiz
COPY scripts ./scripts

# Persisted runtime state (leaderboard + cursor) lives here; mount a volume in prod.
RUN mkdir -p /app/data
ENV STATE_PATH=/app/data/state.json \
    QUESTIONS_PATH=/app/meshquiz/data/questions.json \
    PYTHONUNBUFFERED=1

# Run as non-root
RUN useradd -m -u 10001 buzz && chown -R buzz:buzz /app
USER buzz

CMD ["python", "-m", "meshquiz"]
