import sys
import time

import schedule
from dotenv import load_dotenv

from app import SCHEDULE_TIME, SCHEDULE_WEEKDAYS_ONLY, load_webhooks
from menu_logic import fetch_menu_data, parse_menu, send_message

load_dotenv()


def run_once():
    webhooks = [webhook for webhook in load_webhooks() if webhook.active_yn == 1]
    if not webhooks:
        print("webhooks.json에 활성화된 전송 대상이 없습니다.")
        return

    print("1. 식단 데이터 조회 중...")
    raw = fetch_menu_data()

    print("2. 식단 데이터 파싱 중...")
    menu = parse_menu(raw)

    print(f"3. 총 {len(webhooks)}개 대상에게 전송 시작...")
    for index, webhook in enumerate(webhooks, start=1):
        status = send_message(webhook.webhook_url, menu)
        print(f"   - [{index}] {webhook.name}: {status}")


def run_with_schedule():
    if SCHEDULE_WEEKDAYS_ONLY:
        print(f"평일(월-금) {SCHEDULE_TIME}에 식단을 자동 발송합니다.")
        for weekday in (
            schedule.every().monday,
            schedule.every().tuesday,
            schedule.every().wednesday,
            schedule.every().thursday,
            schedule.every().friday,
        ):
            weekday.at(SCHEDULE_TIME).do(run_once)
    else:
        print(f"매일 {SCHEDULE_TIME}에 식단을 자동 발송합니다.")
        schedule.every().day.at(SCHEDULE_TIME).do(run_once)

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--schedule":
        run_with_schedule()
    else:
        run_once()
