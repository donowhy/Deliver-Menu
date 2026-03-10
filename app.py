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

# --- [DB 설정] ---
DATABASE_URL = os.getenv("DATABASE_URL")
DATABASE_KEY = os.getenv("DATABASE_KEY")
DATABASE_URL.replace("PASSWORD", DATABASE_KEY)
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if not DATABASE_URL:
    DATABASE_URL = "sqlite:///webhooks.db"

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- [모델 정의] ---
class Webhook(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(500), nullable=False)
    name = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

with app.app_context():
    db.create_all()

# --- [식단 관련 로직] ---
OPER_CD = os.getenv("OPER_CD")
ASSIGN_CD = os.getenv("ASSIGN_CD")
SCHEDULE_TIME = os.getenv("SCHEDULE_TIME")
menuWebUrl = os.getenv("MENU_WEB_URL")
def fetch_menu_data():
    url = menuWebUrl
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
    except:
        return None

def format_menu_list(main_dish, side_dishes):
    sides = side_dishes.replace(",", "\n").replace(" ", "\n")
    side_list = [s.strip() for s in sides.split("\n") if s.strip()]
    return f"{main_dish}\n" + "\n".join(side_list)

def parse_menu(raw_data):
    if not raw_data or "data" not in raw_data: return "정보 없음"
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
    """모든 등록된 웹훅으로 메시지 전송"""
    with app.app_context():
        webhooks = Webhook.query.all()
        if not webhooks:
            print("등록된 웹훅이 없습니다.")
            return
        
        print(f"[{datetime.now()}] 식단 데이터 조회 중...")
        raw = fetch_menu_data()
        if not raw:
            print("데이터 조회 실패")
            return
        
        message = parse_menu(raw)
        for wh in webhooks:
            try:
                res = requests.post(wh.url, json={"text": message})
                print(f"전송 성공: {wh.name} (상태: {res.status_code})")
            except Exception as e:
                print(f"전송 실패 {wh.name}: {e}")

# --- [웹 라우트] ---
@app.route('/')
def index():
    webhooks = Webhook.query.order_by(Webhook.created_at.desc()).all()
    return render_template('index.html', webhooks=webhooks)

@app.route('/add', methods=['POST'])
def add_webhook():
    url = request.form.get('url')
    name = request.form.get('name')
    if url:
        new_wh = Webhook(url=url, name=name)
        db.session.add(new_wh)
        db.session.commit()
        flash('웹훅이 등록되었습니다.')
    return redirect(url_for('index'))

@app.route('/delete/<int:id>')
def delete_webhook(id):
    wh = Webhook.query.get(id)
    if wh:
        db.session.delete(wh)
        db.session.commit()
        flash('웹훅이 삭제되었습니다.')
    return redirect(url_for('index'))

@app.route('/test-send')
def test_send():
    send_to_all_webhooks()
    flash('테스트 전송이 완료되었습니다.')
    return redirect(url_for('index'))

# --- [스케줄러 쓰레드] ---
def run_scheduler():
    schedule.every().day.at(SCHEDULE_TIME).do(send_to_all_webhooks)
    print(f"[{datetime.now()}] 스케줄러 가동 중... (매일 {SCHEDULE_TIME} 예약)")
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == '__main__':
    # 터미널에서 python app.py --now 라고 실행하면 즉시 전송 후 종료
    if len(sys.argv) > 1 and sys.argv[1] == '--now':
        print("즉시 전송 모드를 시작합니다...")
        send_to_all_webhooks()
        sys.exit(0)
    
    # 일반 실행 (서버 + 스케줄러)
    t = threading.Thread(target=run_scheduler)
    t.daemon = True
    t.start()
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
