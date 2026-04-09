import os
import sys
import time
import threading
import logging
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
logger = logging.getLogger(__name__)

# --- [DB 설정] ---
def build_database_url():
    database_url = os.getenv("DATABASE_URL")
    database_key = os.getenv("DATABASE_KEY") or os.getenv("KEY")

    if database_url:
        if database_key:
            database_url = database_url.replace("PASSWORD", database_key).replace("[PASSWORD]", database_key)
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        return database_url

    mysql_password = os.getenv("MYSQL_PASSWORD") or os.getenv("MYSQL_ROOT_PASSWORD")
    mysql_user = os.getenv("MYSQL_USER", "root")
    mysql_host = os.getenv("MYSQL_HOST", "db")
    mysql_port = os.getenv("MYSQL_PORT", "3306")
    mysql_database = os.getenv("MYSQL_DATABASE", "menu_deliver")

    if mysql_password:
        return f"mysql+pymysql://{mysql_user}:{mysql_password}@{mysql_host}:{mysql_port}/{mysql_database}?charset=utf8mb4"

    return "sqlite:///webhooks.db"

DATABASE_URL = build_database_url()

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- [모델 정의] ---
class Webhook(db.Model):
    __tablename__ = "TB_WEBHOOK_CONFIG"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    webhook_url = db.Column(db.String(2000), nullable=False)
    active_yn = db.Column(db.Integer, nullable=False, default=1)
    name = db.Column(db.String(100), nullable=False)

# DB 초기화
try:
    with app.app_context():
        db.create_all()
except Exception as e:
    logger.exception("DB 연결 또는 초기화 실패: %s", e)

# --- [발송 작업] ---
SCHEDULE_TIME = os.getenv("SCHEDULE_TIME", "07:50")

def send_to_all_webhooks():
    """DB 웹훅 + ENV 웹훅 모두에게 발송"""
    target_urls = []
    
    # 1. DB에서 웹훅 가져오기
    try:
        with app.app_context():
            db_webhooks = Webhook.query.filter_by(active_yn=1).all()
            for wh in db_webhooks:
                target_urls.append((wh.webhook_url, f"[DB] {wh.name}"))
    except Exception as e:
        logger.exception("DB 웹훅 조회 실패: %s", e)

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
        webhooks = Webhook.query.order_by(Webhook.id.desc()).all()
    except Exception as e:
        logger.exception("웹훅 목록 조회 실패: %s", e)
        webhooks = []

    db_type = "MySQL"
    return render_template('index.html', webhooks=webhooks, db_type=db_type, schedule_time=SCHEDULE_TIME)

@app.route('/add', methods=['POST'])
def add_webhook():
    name = request.form.get('name')
    webhook_url = request.form.get('webhook_url')

    if name and webhook_url:
        try:
            db.session.add(Webhook(
                name=name,
                webhook_url=webhook_url,
                active_yn=1
            ))
            db.session.commit()
            flash(f'{name} 등록 완료')
        except Exception as e:
            db.session.rollback()
            flash(f'DB 저장 실패: {e}')

    return redirect(url_for('index'))

@app.route('/delete/<int:id>')
def delete_webhook(id):
    try:
        wh = Webhook.query.get(id)
        if wh:
            db.session.delete(wh)
            db.session.commit()
            flash('삭제 완료')
    except Exception as e:
        db.session.rollback()
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
