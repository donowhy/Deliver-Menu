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
# Render 설정에서 DATABASE_URL과 DATABASE_KEY(비밀번호)를 가져옵니다.
DATABASE_URL = os.getenv("DATABASE_URL")
DATABASE_KEY = os.getenv("DATABASE_KEY")

if DATABASE_URL:
    # 1. 비밀번호 치환 (URL 안에 [PASSWORD] 또는 PASSWORD 라는 문자열이 있다면 DATABASE_KEY로 교체)
    if DATABASE_KEY:
        DATABASE_URL = DATABASE_URL.replace("PASSWORD", DATABASE_KEY).replace("[PASSWORD]", DATABASE_KEY)
    
    # 2. SQLAlchemy 1.4+ 호환성을 위해 postgres://를 postgresql://로 변환
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
else:
    # DATABASE_URL이 아예 없을 경우 로컬 DB 사용
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
    type = db.Column(db.String(20), nullable=False) # CHAT or CHANNEL
    created_at = db.Column(db.DateTime, default=datetime.now)

with app.app_context():
    db.create_all()

# --- [식단 관련 로직] ---
OPER_CD = os.getenv("OPER_CD", "O000002")
ASSIGN_CD = os.getenv("ASSIGN_CD", "S000545")
SCHEDULE_TIME = os.getenv("SCHEDULE_TIME", "07:50")

def fetch_menu_data():
    url = "https://puls2.pulmuone.com/src/sql/menu/week_sql.php"
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
    """DB에 등록된 모든 웹훅으로 전송"""
    with app.app_context():
        webhooks = Webhook.query.all()
        if not webhooks:
            print("전송할 웹훅이 DB에 없습니다.")
            return
        
        raw = fetch_menu_data()
        if not raw: return
        
        message = parse_menu(raw)
        for wh in webhooks:
            try:
                requests.post(wh.key, json={"text": message})
                print(f"전송 성공: [{wh.type}] {wh.name}")
            except Exception as e:
                print(f"전송 실패 {wh.name}: {e}")

# --- [웹 라우트] ---
@app.route('/')
def index():
    webhooks = Webhook.query.order_by(Webhook.created_at.desc()).all()
    return render_template('index.html', webhooks=webhooks)

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
    flash('DB에 등록된 모든 웹훅으로 테스트 전송을 보냈습니다.')
    return redirect(url_for('index'))

# --- [스케줄러 쓰레드] ---
def run_scheduler():
    schedule.every().day.at(SCHEDULE_TIME).do(send_to_all_webhooks)
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
