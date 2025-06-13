FROM python:3.10-slim

WORKDIR /app
RUN pip install --upgrade pip
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["celery", "-A", "analyzer_worker:celery", "worker", "-Q", "analyzer_queue", "--loglevel=info", "--concurrency=1","--pool=solo"]