import os
import sys
import time
import schedule
from datetime import datetime
from dotenv import load_dotenv

# 핵심 로직 불러오기
from menu_logic import fetch_menu_data, parse_menu, send_message

# .env 로드
load_dotenv()

def run_once():
    """즉시 식단을 조회하여 .env에 설정된 모든 웹훅으로 발송합니다."""
    raw_urls = os.getenv("WEBHOOK_URLS", "")
    env_urls = [url.strip() for url in raw_urls.split(",") if url.strip()]
    
    if not env_urls:
        print("!!! 에러: .env 파일에 WEBHOOK_URLS가 설정되어 있지 않습니다.")
        return

    print(f"[{datetime.now()}] 즉시 발송 모드 시작...")
    print("1. 식단 데이터 조회 중...")
    raw = fetch_menu_data()
    
    print("2. 데이터 파싱 중...")
    message = parse_menu(raw)
    
    print(f"3. 총 {len(env_urls)}개의 웹훅으로 전송 시작...")
    for i, url in enumerate(env_urls):
        status = send_message(url, message)
        print(f"   - [{i+1}] 전송 결과: {status}")
    
    print(f"[{datetime.now()}] 작업 완료.")

def run_with_schedule():
    """설정된 시간에 맞춰 매일 반복 실행합니다."""
    schedule_time = os.getenv("SCHEDULE_TIME", "07:50")
    
    print(f"--- [예약 발송 모드 활성화] ---")
    print(f"매일 오전 {schedule_time}에 발송됩니다. (터미널을 종료하지 마세요)")
    
    schedule.every().day.at(schedule_time).do(run_once)
    
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    # 인자값 확인 (--schedule 이 있으면 예약 모드, 없으면 즉시 실행)
    if len(sys.argv) > 1 and sys.argv[1] == "--schedule":
        try:
            run_with_schedule()
        except KeyboardInterrupt:
            print("\n스케줄러를 종료합니다.")
    else:
        run_once()
