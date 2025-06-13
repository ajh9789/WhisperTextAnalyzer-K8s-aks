import os  # 환경변수 접근을 위한 모듈
import redis  # Redis에 직접 publish 하기 위한 모듈
from celery import Celery  # Celery 비동기 작업을 위한 모듈
from transformers import pipeline  # Huggingface의 사전 학습 모델 파이프라인 모듈

REDIS_HOST = os.getenv("REDIS_HOST", "redis" if os.getenv("DOCKER") else "localhost")  # Redis 주소 환경변수에서 읽기 (도커 여부 고려)
REDIS_PORT = 6379  # Redis 포트 설정 (기본 6379)
celery = Celery("analyzer_worker", broker=f"redis://{REDIS_HOST}:{REDIS_PORT}/0")  # Celery 앱 인스턴스 생성 (Redis를 브로커로 사용)
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)  # Redis publish용 동기 클라이언트 인스턴스 생성

# 감정 분석용 Transformers 파이프라인 모델 초기화
classifier = pipeline("sentiment-analysis", model="distilbert/distilbert-base-uncased-finetuned-sst-2-english", )


@celery.task(name="analyzer_worker.analyzer_text", queue="analyzer_queue")  # Celery 태스크로 analyzer_texS 등록
def analyzer_text(text):  # 텍스트 감정 분석 및 Redis 전송 함수 정의
    print("[STT] → [Analyzer] Celery 전달 text 수신")
    try:
        decoded_text = text  # 받은 텍스트를 처리용 변수에 저장 (디코딩 생략됨)
        print(f"[Analyzer] 🎙️ 텍스트 수신: {decoded_text}")
        result = classifier(decoded_text)[0]  # 감정 분석 모델을 사용해 텍스트 분류 수행
    except Exception as e:
        print(f"[Analyzer] Sentiment analysis error: {e}")
        return

    emotion = ("긍정" if result["label"] == "POSITIVE" else "부정")  # 분류 결과를 바탕으로 긍정/부정 레이블 결정
    icon = ("👍" if result["label"] == "POSITIVE" else "👎")  # 이모지 아이콘 설정 (👍 또는 👎)
    score = result["score"]

    output = f"{icon} {emotion} [{score * 100:.0f}%] : {decoded_text}"  # 출력 문자열 구성 (예: 긍정/부정 + 점수 + 원문)
    try:
        r.publish("result_channel", output)  # 결과를 Redis PubSub 채널로 전송
    except Exception as e:
        print(f"[Analyzer] Redis publish error: {e}")
        return
    print(f"[Analyzer] ✅ publish 완료: {output}")  # 전송 완료 로그 출력
