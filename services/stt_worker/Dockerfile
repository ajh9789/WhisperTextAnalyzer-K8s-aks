FROM python:3.10-slim

# 시스템 패키지 설치 (whisper.cpp 빌드 및 모델 다운로드용)
RUN apt-get update && apt-get install -y \
    git \
    cmake \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# whisper.cpp 소스 다운로드 및 빌드
WORKDIR /app
RUN git clone https://github.com/ggerganov/whisper.cpp.git
WORKDIR /app/whisper.cpp
RUN make

# medium 모델 다운로드 (약 1.5GB) 테스트는 스몰
WORKDIR /app
RUN mkdir -p /app/models && \
    curl -L -o /app/models/ggml-small.bin \
    https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin

# 애플리케이션 코드 복사
COPY . /app

# Celery 워커 실행 (STT 전용)
CMD ["celery", "-A", "stt_worker", "worker", "--loglevel=info", "-Q", "stt_queue"]