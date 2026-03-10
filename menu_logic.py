import os
import json
import requests
from datetime import datetime

def fetch_menu_data():
    """풀무원 서버에서 식단 원본 데이터를 가져옵니다."""
    url = os.getenv("MENU_WEB_URL", "https://puls2.pulmuone.com/src/sql/menu/week_sql.php")
    oper_cd = os.getenv("OPER_CD", "O000002")
    assign_cd = os.getenv("ASSIGN_CD", "S000545")
    
    request_param = {"topOperCd": oper_cd, "topAssignCd": assign_cd, "menuDay": 0}
    payload = {"requestId": "search_week", "requestMode": "1", "requestParam": json.dumps(request_param)}
    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://puls2.pulmuone.com/src/php/menu/week.php"
    }
    try:
        response = requests.post(url, data=payload, headers=headers)
        return response.json()
    except Exception as e:
        print(f"데이터 조회 에러: {e}")
        return None

def format_menu_list(main_dish, side_dishes):
    """메인 요리와 반찬을 개행 문자로 정렬합니다."""
    sides = side_dishes.replace(",", "\n").replace(" ", "\n")
    side_list = [s.strip() for s in sides.split("\n") if s.strip()]
    return f"{main_dish}\n" + "\n".join(side_list)

def parse_menu(raw_data):
    """데이터를 읽어 팀즈 전송용 메시지로 변환합니다."""
    if not raw_data or "data" not in raw_data:
        return "오늘의 식단 정보를 가져올 수 없습니다."
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    results = {"lunch_salad": "정보 없음", "lunch_main": "정보 없음", "dinner": "정보 없음"}
    
    for item in raw_data["data"]:
        meal_type, main_dish, side_dishes = item[1], item[3], item[5]
        if "중식 샐러드팩" in meal_type:
            results["lunch_salad"] = main_dish
        elif "중식 일반메뉴" in meal_type:
            results["lunch_main"] = format_menu_list(main_dish, side_dishes)
        elif "석식 일반메뉴" in meal_type:
            results["dinner"] = format_menu_list(main_dish, side_dishes)
    
    msg = f"🍱 {today_str} 오늘의 식단표\n에스엘 식당 메뉴 안내\n\n"
    msg += f"🥗 중식 (샐러드)\n{results['lunch_salad']}\n\n"
    msg += f"🍱 중식 (일반)\n{results['lunch_main']}\n\n"
    msg += f"🌙 석식 (일반)\n{results['dinner']}"
    return msg

def send_message(url, message):
    """실제 웹훅 URL로 메시지를 전송합니다."""
    try:
        res = requests.post(url, json={"text": message})
        return res.status_code
    except Exception as e:
        print(f"발송 실패: {e}")
        return None
