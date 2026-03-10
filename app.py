import os
import sys
import time
import threading
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
import schedule

# 분리한 핵심 로직 불러오기
from menu_logic import fetch_menu_data, parse_menu, send_message

# .env 로드
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "your-super-secret-key-123")

# --- [DB 설정] ---
DATABASE_URL = os.getenv("DATABASE_URL")
DATABASE_KEY = os.getenv("DATABASE_KEY") or os.getenv("KEY")

if DATABASE_URL:
    if DATABASE_KEY:
        DATABASE_URL = DATABASE_URL.replace("PASSWORD", DATABASE_KEY).replace("[PASSWORD]", DATABASE_KEY)
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
else:
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

# DB 초기화
try:
    with app.app_context():
        db.create_all()
except Exception as e:
    print(f"!!! DB 연결 실패: {e}")

# --- [발송 작업] ---
SCHEDULE_TIME = os.getenv("SCHEDULE_TIME", "07:50")

def send_to_all_webhooks():
    """DB 웹훅 + ENV 웹훅 모두에게 발송"""
    target_urls = []
    
    # 1. DB에서 웹훅 가져오기
    try:
        with app.app_context():
            db_webhooks = Webhook.query.all()
            for wh in db_webhooks:
                target_urls.append((wh.key, f"[DB:{wh.type}] {wh.name}"))
    except:
        pass

    # 2. ENV에서 웹훅 가져오기 (테스트용)
    raw_urls = os.getenv("WEBHOOK_URLS", "")
    env_urls = [url.strip() for url in raw_urls.split(",") if url.strip()]
    for i, url in enumerate(env_urls):
        target_urls.append((url, f"[ENV] 테스트웹훅_{i+1}"))
            
    if not target_urls:
        print("발송할 대상이 없습니다.")
        return
    
    # 데이터 조회 및 파싱
    raw = fetch_menu_data()
    message = parse_menu(raw)
    
    # 순차 발송
    for url, label in target_urls:
        status = send_message(url, message)
        print(f"[{datetime.now()}] {label} 발송 결과: {status}")

# --- [웹 라우트] ---
@app.route('/')
def index():
    try:
        webhooks = Webhook.query.order_by(Webhook.created_at.desc()).all()
    except:
        webhooks = []
    db_type = "Supabase(Postgres)" if "postgresql" in DATABASE_URL else "Local(SQLite)"
    return render_template('index.html', webhooks=webhooks, db_type=db_type)

@app.route('/add', methods=['POST'])
def add_webhook():
    name, key, wh_type = request.form.get('name'), request.form.get('key'), request.form.get('type')
    if name and key and wh_type:
        try:
            db.session.add(Webhook(name=name, key=key, type=wh_type))
            db.session.commit()
            flash(f'[{wh_type}] {name} 등록 완료')
        except Exception as e:
            flash(f'DB 저장 실패: {e}')
    return redirect(url_for('index'))

@app.route('/delete/<int:pk>')
def delete_webhook(pk):
    try:
        wh = Webhook.query.get(pk)
        if wh:
            db.session.delete(wh)
            db.session.commit()
            flash('삭제 완료')
    except Exception as e:
        flash(f'삭제 실패: {e}')
    return redirect(url_for('index'))

@app.route('/test-send')
def test_send():
    send_to_all_webhooks()
    flash('테스트 발송 요청 완료')
    return redirect(url_for('index'))

# --- [스케줄러 쓰레드] ---
def run_scheduler():
    schedule.every().day.at(SCHEDULE_TIME).do(send_to_all_webhooks)
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == '__main__':
    # 즉시 실행 모드 (--now)
    if len(sys.argv) > 1 and sys.argv[1] == '--now':
        send_to_all_webhooks()
        sys.exit(0)
    
    # 서버 실행
    t = threading.Thread(target=run_scheduler)
    t.daemon = True
    t.start()
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
