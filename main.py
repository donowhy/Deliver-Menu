import sys
from dotenv import load_dotenv
from menu_logic import fetch_menu_data, parse_menu, send_message
import os

# .env 로드
load_dotenv()

def run_now():
    """현재 설정된 환경 변수를 바탕으로 즉시 발송합니다."""
    raw_urls = os.getenv("WEBHOOK_URLS", "")
    env_urls = [url.strip() for url in raw_urls.split(",") if url.strip()]
    
    if not env_urls:
        print("발송할 WEBHOOK_URLS가 .env에 없습니다.")
        return

    print("식단 데이터 조회 중...")
    raw = fetch_menu_data()
    message = parse_menu(raw)
    
    for i, url in enumerate(env_urls):
        status = send_message(url, message)
        print(f"[{i+1}] 전송 결과: {status}")

if __name__ == "__main__":
    run_now()
