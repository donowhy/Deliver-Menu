import os
import requests
import json
import schedule
import time
from datetime import datetime
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# --- [환경 변수 설정] ---
# 여러 개의 웹훅 URL은 쉼표(,)로 구분된 문자열로 가져와서 리스트로 변환합니다.
raw_webhook_urls = os.getenv("WEBHOOK_URLS", "")
WEBHOOK_URLS = [url.strip() for url in raw_webhook_urls.split(",") if url.strip()]

OPER_CD = os.getenv("OPER_CD", "O000002")
ASSIGN_CD = os.getenv("ASSIGN_CD", "S000545")
SCHEDULE_TIME = os.getenv("SCHEDULE_TIME", "07:50")
# ------------------

def fetch_menu_data():
    """풀무원 서버에서 원본 데이터를 가져옵니다."""
    url = "https://puls2.pulmuone.com/src/sql/menu/week_sql.php"

    request_param = {
        "topOperCd": OPER_CD,
        "topAssignCd": ASSIGN_CD,
        "menuDay": 0, # 0: 오늘
        "srchCurShopclsCd": "",
        "custCd": ""
    }

    payload = {
        "requestId": "search_week",
        "requestMode": "1",
        "requestParam": json.dumps(request_param)
    }

    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
        "Referer": "https://puls2.pulmuone.com/src/php/menu/week.php"
    }

    try:
        response = requests.post(url, data=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"[{datetime.now()}] 데이터 가져오기 실패: {e}")
        return None

def format_menu_list(main_dish, side_dishes):
    """메인 요리와 반찬 리스트를 개행 문자로 정렬합니다."""
    # 반찬 리스트가 공백이나 콤마로 구분되어 있을 경우 줄바꿈으로 변환
    sides = side_dishes.replace(",", "\n").replace(" ", "\n")
    # 중복 공백 제거 및 깔끔하게 정리
    side_list = [s.strip() for s in sides.split("\n") if s.strip()]
    return f"{main_dish}\n" + "\n".join(side_list)

def parse_menu(raw_data):
    """데이터에서 필요한 중식/석식 메뉴를 추출하여 원하는 텍스트 포맷으로 만듭니다."""
    if not raw_data or "data" not in raw_data:
        return "데이터를 찾을 수 없습니다."

    today_str = datetime.now().strftime("%Y-%m-%d")
    menu_list = raw_data["data"]

    results = {
        "lunch_salad": "정보 없음",
        "lunch_main": "정보 없음",
        "dinner": "정보 없음"
    }

    for item in menu_list:
        meal_type = item[1]
        main_dish = item[3]
        side_dishes = item[5]

        if "중식 샐러드팩" in meal_type:
            results["lunch_salad"] = main_dish
        elif "중식 일반메뉴" in meal_type:
            results["lunch_main"] = format_menu_list(main_dish, side_dishes)
        elif "석식 일반메뉴" in meal_type:
            results["dinner"] = format_menu_list(main_dish, side_dishes)

    # 최종 메시지 구성
    message = f"🍱 {today_str} 오늘의 식단표\n"
    message += "에스엘 식당 메뉴 안내 (세로 모드)\n\n"

    message += "🥗 중식 (샐러드)\n"
    message += f"{results['lunch_salad']}\n\n"

    message += "🍱 중식 (일반)\n"
    message += f"{results['lunch_main']}\n\n"

    message += "🌙 석식 (일반)\n"
    message += f"{results['dinner']}"

    return message

def send_to_webhooks(message_text):
    """설정된 모든 웹훅 URL로 메시지를 전송합니다."""
    if not WEBHOOK_URLS:
        print("설정된 웹훅 URL이 없습니다. 결과만 출력합니다.")
        print(message_text)
        return

    message_card = {
        "text": message_text
    }

    for url in WEBHOOK_URLS:
        try:
            res = requests.post(url, json=message_card)
            if res.status_code in [200, 202]:
                print(f"[{datetime.now()}] 알림 전송 성공! (URL: {url[:30]}...)")
            else:
                print(f"[{datetime.now()}] 전송 실패 ({res.status_code}): {res.text}")
        except Exception as e:
            print(f"[{datetime.now()}] 전송 중 오류 발생 ({url[:30]}...): {e}")

def job():
    """매일 정해진 시간에 실행될 메인 작업입니다."""
    print(f"[{datetime.now()}] 식단 배달을 시작합니다...")
    raw = fetch_menu_data()
    if raw:
        message = parse_menu(raw)
        send_to_webhooks(message)
    else:
        print("식단 정보를 가져오지 못해 작업을 중단합니다.")

if __name__ == "__main__":
    # 실행 시 한 번 즉시 테스트 (필요 시)
    # job()

    # .env에 설정된 시간에 실행 예약
    schedule.every().day.at(SCHEDULE_TIME).do(job)

    print(f"[{datetime.now()}] 식단 도우미 대기 중... (매일 {SCHEDULE_TIME} 예약)")
    while True:
        schedule.run_pending()
        time.sleep(60)
