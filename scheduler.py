import os
import time
import schedule
from app import send_to_all_webhooks

schedule_time = os.getenv("SCHEDULE_TIME", "07:50")
print(f"[scheduler] every day at {schedule_time}")

schedule.every().day.at(schedule_time).do(send_to_all_webhooks)

while True:
    schedule.run_pending()
    time.sleep(60)