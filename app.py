import json
import os
import sys
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

import schedule
from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, url_for

from menu_logic import fetch_menu_data, parse_menu, send_message


def get_runtime_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


BASE_DIR = get_runtime_dir()
load_dotenv(BASE_DIR / ".env")

app = Flask(__name__)

SCHEDULE_TIME = os.getenv("SCHEDULE_TIME", "07:55")
SCHEDULE_WEEKDAYS_ONLY = os.getenv("SCHEDULE_WEEKDAYS_ONLY", "true").strip().lower() not in {
    "0",
    "false",
    "no",
    "off",
}


def resolve_webhook_file_path():
    raw_path = os.getenv("WEBHOOK_FILE", "webhooks.json").strip() or "webhooks.json"
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate
    return BASE_DIR / candidate


WEBHOOK_FILE_PATH = resolve_webhook_file_path()


@dataclass
class WebhookRecord:
    id: int
    name: str
    webhook_url: str
    active_yn: int = 1


def build_redirect_url(message):
    if not message:
        return url_for("index")
    return f"{url_for('index')}?{urlencode({'message': message})}"


def ensure_webhook_store():
    if WEBHOOK_FILE_PATH.exists():
        return

    WEBHOOK_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    WEBHOOK_FILE_PATH.write_text("[]", encoding="utf-8")


def load_webhooks():
    ensure_webhook_store()

    try:
        raw_items = json.loads(WEBHOOK_FILE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    webhooks = []
    for index, item in enumerate(raw_items, start=1):
        try:
            if isinstance(item, str):
                webhooks.append(
                    WebhookRecord(
                        id=index,
                        name=f"Imported webhook {index}",
                        webhook_url=item,
                    )
                )
                continue

            webhooks.append(
                WebhookRecord(
                    id=int(item["id"]),
                    name=str(item["name"]),
                    webhook_url=str(item["webhook_url"]),
                    active_yn=int(item.get("active_yn", 1)),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue

    return sorted(webhooks, key=lambda webhook: webhook.id, reverse=True)


def save_webhooks(webhooks):
    ensure_webhook_store()
    payload = [asdict(webhook) for webhook in sorted(webhooks, key=lambda item: item.id)]
    WEBHOOK_FILE_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def next_webhook_id(webhooks):
    return max((webhook.id for webhook in webhooks), default=0) + 1


def send_to_all_webhooks():
    target_webhooks = [webhook for webhook in load_webhooks() if webhook.active_yn == 1]
    if not target_webhooks:
        print("No active webhooks configured.")
        return

    raw = fetch_menu_data()
    menu = parse_menu(raw)

    for webhook in target_webhooks:
        status = send_message(webhook.webhook_url, menu)
        print(f"[{datetime.now()}] {webhook.name}: {status}")


@app.route("/")
def index():
    return render_template(
        "index.html",
        webhooks=load_webhooks(),
        schedule_time=SCHEDULE_TIME,
        schedule_weekdays_only=SCHEDULE_WEEKDAYS_ONLY,
        store_name=WEBHOOK_FILE_PATH.name,
        store_path=str(WEBHOOK_FILE_PATH),
        message=(request.args.get("message") or "").strip(),
    )


@app.route("/add", methods=["POST"])
def add_webhook():
    name = (request.form.get("name") or "").strip()
    webhook_url = (request.form.get("webhook_url") or "").strip()

    if not name or not webhook_url:
        return redirect(build_redirect_url("이름과 Webhook URL을 모두 입력해 주세요."))

    webhooks = load_webhooks()
    webhooks.append(
        WebhookRecord(
            id=next_webhook_id(webhooks),
            name=name,
            webhook_url=webhook_url,
            active_yn=1,
        )
    )
    save_webhooks(webhooks)
    return redirect(build_redirect_url(f"{name} 등록 완료"))


@app.route("/delete/<int:webhook_id>")
def delete_webhook(webhook_id):
    webhooks = load_webhooks()
    filtered = [webhook for webhook in webhooks if webhook.id != webhook_id]

    if len(filtered) == len(webhooks):
        return redirect(build_redirect_url("삭제할 webhook을 찾지 못했습니다."))

    save_webhooks(filtered)
    return redirect(build_redirect_url("삭제 완료"))


@app.route("/test-send")
def test_send():
    send_to_all_webhooks()
    return redirect(build_redirect_url("테스트 발송 요청 완료"))


def run_scheduler():
    if SCHEDULE_WEEKDAYS_ONLY:
        for weekday in (
            schedule.every().monday,
            schedule.every().tuesday,
            schedule.every().wednesday,
            schedule.every().thursday,
            schedule.every().friday,
        ):
            weekday.at(SCHEDULE_TIME).do(send_to_all_webhooks)
    else:
        schedule.every().day.at(SCHEDULE_TIME).do(send_to_all_webhooks)

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    ensure_webhook_store()

    if len(sys.argv) > 1 and sys.argv[1] == "--now":
        send_to_all_webhooks()
        sys.exit(0)

    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()

    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
