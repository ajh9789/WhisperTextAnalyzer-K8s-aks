import os  # 운영체제 환경변수 접근을 위한 모듈
import re  # 정규표현식 처리 모듈
import numpy as np  # 오디오 데이터를 배열로 처리하기 위한 numpy 모듈
from scipy.io.wavfile import write  # numpy 배열을 wav 파일로 저장하기 위한 write 함수
# import whisper as openai_whisper  # OpenAI Whisper 모델 불러오기 whisper.cpp로 전환
from celery import Celery  # 비동기 작업 처리를 위한 Celery 모듈
import tempfile  # 임시 파일 생성용 모듈
from collections import Counter

# from collections import deque

# 기본 설정
REDIS_HOST = os.getenv("REDIS_HOST", "redis" if os.getenv("DOCKER") else "localhost")  # Redis 주소 환경 변수로 설정 (도커 환경 고려)
celery = Celery("stt_worker", broker=f"redis://{REDIS_HOST}:6379/0")  # Celery 앱 인스턴스 생성 및 Redis 브로커 설정

# Whisper 모델 로드 whisper.cpp로 전환
#model_size = os.getenv("MODEL_SIZE", "tiny")  # Whisper 모델 사이즈 설정 (tiny, base 등)
#model_path = os.getenv("MODEL_PATH", "/app/models")  # 모델 다운로드 저장 경로 지정
#os.makedirs(model_path, exist_ok=True)  # 모델 저장 경로가 없을 경우 생성
# 기존 openai-whisper 모델 사용 코드 (미사용)
# model = openai_whisper.load_model(model_size, download_root=model_path)  # Whisper 모델 로드 및 다운로드
# → whisper.cpp에서는 CLI로 처리되므로 삭제 가능


# 메모리 내 4초 누적 버퍼 (deque로 변경) 웹서버에서 받는걸로 결정 다중이용자 고려하기 편함
# buffer = deque()


# ✅ 반복 텍스트 필터 함수
def is_repetitive(text: str) -> bool:
    # 1. 문자 반복 검사:
    # 공백을 제거한 후 같은 문자가 5번 이상 반복되면 반복으로 간주
    # 예: "ㅋㅋㅋㅋㅋ", "아아아아아"
    if re.fullmatch(r"(.)\1{4,}", text.replace(" ", "")):
        return True

    # 2. 단어 반복 검사:
    # 공백 기준으로 같은 단어가 연속적으로 5회 이상 반복될 경우 필터링
    # 예: "좋아요 좋아요 좋아요 좋아요 좋아요"
    if re.search(r"\b(\w+)\b(?: \1){4,}", text):
        return True

    # 3. 음절 반복 검사:
    # 같은 음절이 공백 포함 형태로 반복되는 경우 필터링
    # 예: "아 아 아 아 아"
    if re.fullmatch(r"(.)\s*(?:\1\s*){4,}", text):
        return True

    # 4. 단어 빈도 기반 반복 검사:
    # 문장에서 특정 단어가 전체 단어의 30% 이상, 5회 이상 등장할 경우 필터
    words = re.findall(r"\b\w+\b", text)
    total = len(words)
    if total >= 5:
        freq = Counter(words)
        most_common, count = freq.most_common(1)[0]
        if count / total > 0.2 and count >= 5:
            return True
    # 5. n-gram 반복 검사:
    # 2단어, 3단어씩 묶인 문장이 반복되는 경우 필터링
    # 예: "스튜디오에 도착한 스튜디오에 도착한 ..."
    if is_ngram_repetitive(text, n=2):
        return True
    if is_ngram_repetitive(text, n=3):
        return True
    return False


# n-gram 각 문장을 n개씩 조개서 문장 단위로 체크하는 for문과 갯수체크하는 counter로 이뤄어진 O(n)와 nlogn정도
def is_ngram_repetitive(text: str, n=2) -> bool:
    words = text.split()  # 공백 기준 단어 분리  # n-gram 단위 반복 필터 함수
    # n개의 단어를 묶어서 n-gram 리스트 구성, #ex: "스튜디오에 도착한 스튜디오에 도착한" → 3단어 단위 n-gram 반복
    ngrams = [" ".join(words[i: i + n]) for i in range(len(words) - n + 1)]
    if not ngrams:
        return False
    freq = Counter(ngrams)  # n-gram 빈도 측정 (ex: '스튜디오에 도착한': 8회 등)
    most_common, count = freq.most_common(1)[0]  # 가장 많이 나온 n-gram 추출 most_common은 리스트형
    if count >= 5 and count / len(ngrams) > 0.2:  # ({'스튜디오에 도착한': 3, '도착한 후': 1}) 같은 딕셔너리 형태의 튜플로 추출
        return True  # 전체 n-gram 중 특정 문장이 절반 이상 반복되며 5회 이상 등장하면 필터링
    return False


@celery.task(name="stt_worker.transcribe_audio", queue="stt_queue")  # Celery 태스크 등록: STT 작업 함수
def transcribe_audio(audio_bytes):  # STT 오디오 처리 함수 정의
    print("[STT] 🎧 오디오 청크 수신")
    audio_np = np.frombuffer(audio_bytes, dtype=np.int16)  # 'bytes' 데이터를 numpy int16 배열로 변환
    with tempfile.NamedTemporaryFile(suffix=".wav") as tmpfile:  # 오디오 데이터를 임시 WAV 파일로 저장
        write(tmpfile.name, 16000, audio_np.astype(np.int16))  # numpy 배열을 16kHz wav로 저장
        try:
            # ✅ whisper.cpp CLI 실행 방식으로 대체됨
            command = [
                './main',  # whisper.cpp 실행 파일
                '-m', '/app/models/ggml-small.bin',
                '-f', tmpfile.name,
                '-l', 'ko',
                '-otxt'
            ]
            subprocess.run(command, check=True)
            txt_output_path = tmpfile.name.replace('.wav', '.txt')
            with open(txt_output_path, 'r', encoding='utf-8') as f:
                text = f.read().strip()
            os.remove(tmpfile.name)
            os.remove(txt_output_path)
            if not text:  # 공백 결과일 경우 분석 생략
                print("[STT] ⚠️ 공백 텍스트 → 분석 생략")
                return
            if is_repetitive(text):  # 반복 텍스트 필터링 적용
                print(f"[STT] ⚠️ 반복 텍스트 감지 → 분석 생략: {text}")
                return
            print(f"[STT] 🎙️ Whisper STT 결과: {text}")

        except Exception as e:
            print(f"[STT] ❌ Whisper 처리 실패: {e}")
            return

        try:
            celery.send_task("analyzer_worker.analyzer_text", args=[text], queue="analyzer_queue")
            print("[STT] ✅ analyzer_worker 호출 완료")  # 분석 결과를 analyzer_worker에게 전달
        except Exception as e:
            print(f"[STT] ❌ analyzer_worker 호출 실패: {e}")
