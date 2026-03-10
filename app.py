import os
import sys
import requests
import json
import schedule
import time
import threading
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

# .env 로드
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "your-super-secret-key-123")

# --- [DB 설정 및 환경 변수 체크] ---
DATABASE_URL = os.getenv("DATABASE_URL")
DATABASE_KEY = os.getenv("DATABASE_KEY")
# 테스트용 환경 변수 웹훅
RAW_WEBHOOK_URLS = os.getenv("WEBHOOK_URLS", "")
ENV_WEBHOOKS = [url.strip() for url in RAW_WEBHOOK_URLS.split(",") if url.strip()]

print("--- [환경 변수 로드 확인] ---")
print(f"인식된 변수 목록: {list(os.environ.keys())}") # 어떤 변수들이 들어왔는지 확인

if DATABASE_URL:
    if DATABASE_KEY:
        DATABASE_URL = DATABASE_URL.replace("PASSWORD", DATABASE_KEY).replace("[PASSWORD]", DATABASE_KEY)
        print("DATABASE_KEY를 사용하여 URL 비밀번호를 치환했습니다.")
    
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    
    print(f"Supabase 연결 시도 중...")
else:
    print("경고: DATABASE_URL 환경 변수가 없습니다. 로컬 SQLite를 사용합니다.")
    DATABASE_URL = "sqlite:///webhooks.db"

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- [모델 정의] ---
class Webhook(db.Model):
    pk = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    key = db.Column(db.String(500), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

with app.app_context():
    db.create_all()

# --- [식단 관련 로직] ---
OPER_CD = os.getenv("OPER_CD", "O000002")
ASSIGN_CD = os.getenv("ASSIGN_CD", "S000545")
SCHEDULE_TIME = os.getenv("SCHEDULE_TIME", "07:50")

def fetch_menu_data():
    url = os.getenv("MENU_WEB_URL", "https://puls2.pulmuone.com/src/sql/menu/week_sql.php")
    request_param = {"topOperCd": OPER_CD, "topAssignCd": ASSIGN_CD, "menuDay": 0}
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
    sides = side_dishes.replace(",", "\n").replace(" ", "\n")
    side_list = [s.strip() for s in sides.split("\n") if s.strip()]
    return f"{main_dish}\n" + "\n".join(side_list)

def parse_menu(raw_data):
    if not raw_data or "data" not in raw_data: return "오늘의 식단 정보를 가져올 수 없습니다."
    today_str = datetime.now().strftime("%Y-%m-%d")
    results = {"lunch_salad": "정보 없음", "lunch_main": "정보 없음", "dinner": "정보 없음"}
    for item in raw_data["data"]:
        meal_type, main_dish, side_dishes = item[1], item[3], item[5]
        if "중식 샐러드팩" in meal_type: results["lunch_salad"] = main_dish
        elif "중식 일반메뉴" in meal_type: results["lunch_main"] = format_menu_list(main_dish, side_dishes)
        elif "석식 일반메뉴" in meal_type: results["dinner"] = format_menu_list(main_dish, side_dishes)
    
    msg = f"🍱 {today_str} 오늘의 식단표\n에스엘 식당 메뉴 안내\n\n"
    msg += f"🥗 중식 (샐러드)\n{results['lunch_salad']}\n\n"
    msg += f"🍱 중식 (일반)\n{results['lunch_main']}\n\n"
    msg += f"🌙 석식 (일반)\n{results['dinner']}"
    return msg

def send_to_all_webhooks():
    """DB 웹훅 + ENV 웹훅 모두에게 발송"""
    with app.app_context():
        # 1. DB에서 가져오기
        db_webhooks = Webhook.query.all()
        target_urls = [(wh.key, f"[DB:{wh.type}] {wh.name}") for wh in db_webhooks]
        
        # 2. Env에서 가져오기 (테스트용)
        for i, url in enumerate(ENV_WEBHOOKS):
            target_urls.append((url, f"[ENV] 테스트웹훅_{i+1}"))
            
        if not target_urls:
            print("발송할 대상(DB/ENV)이 전혀 없습니다.")
            return
        
        print(f"총 {len(target_urls)}개의 대상으로 발송을 시작합니다...")
        raw = fetch_menu_data()
        if not raw:
            print("식단 데이터를 가져오지 못했습니다.")
            return
        
        message = parse_menu(raw)
        for url, label in target_urls:
            try:
                res = requests.post(url, json={"text": message})
                print(f"전송 성공: {label} (결과: {res.status_code})")
            except Exception as e:
                print(f"전송 실패 {label}: {e}")

# --- [웹 라우트] ---
@app.route('/')
def index():
    webhooks = Webhook.query.order_by(Webhook.created_at.desc()).all()
    db_type = "Supabase(Postgres)" if "postgresql" in DATABASE_URL else "Local(SQLite)"
    return render_template('index.html', webhooks=webhooks, db_type=db_type)

@app.route('/add', methods=['POST'])
def add_webhook():
    name = request.form.get('name')
    key = request.form.get('key')
    type = request.form.get('type')
    if name and key and type:
        new_wh = Webhook(name=name, key=key, type=type)
        db.session.add(new_wh)
        db.session.commit()
        flash(f'[{type}] {name} 등록 완료')
    return redirect(url_for('index'))

@app.route('/delete/<int:pk>')
def delete_webhook(pk):
    wh = Webhook.query.get(pk)
    if wh:
        db.session.delete(wh)
        db.session.commit()
        flash('삭제 완료')
    return redirect(url_for('index'))

@app.route('/test-send')
def test_send():
    send_to_all_webhooks()
    flash('테스트 발송을 시도했습니다. Render 로그를 확인하세요.')
    return redirect(url_for('index'))

# --- [스케줄러 쓰레드] ---
def run_scheduler():
    schedule.every().day.at(SCHEDULE_TIME).do(send_to_all_webhooks)
    print(f"[{datetime.now()}] 스케줄러 가동 중 (예약: {SCHEDULE_TIME})")
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--now':
        send_to_all_webhooks()
        sys.exit(0)
    
    t = threading.Thread(target=run_scheduler)
    t.daemon = True
    t.start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
