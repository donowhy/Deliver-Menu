import json
import os
from datetime import date, datetime

import requests


def requests_verify():
    return os.getenv("VERIFY_SSL", "true").strip().lower() not in {"0", "false", "no", "off"}


def get_reference_date():
    raw = (os.getenv("REFERENCE_DATE") or "").strip()
    if raw:
        try:
            return date.fromisoformat(raw)
        except ValueError:
            pass
    return datetime.now().date()


def fetch_menu_data(menu_day=0):
    url = os.getenv("MENU_WEB_URL", "https://puls2.pulmuone.com/src/sql/menu/week_sql.php")
    oper_cd = os.getenv("OPER_CD", "O000002")
    assign_cd = os.getenv("ASSIGN_CD", "S000545")

    request_param = {"topOperCd": oper_cd, "topAssignCd": assign_cd, "menuDay": menu_day}
    payload = {
        "requestId": "search_week",
        "requestMode": "1",
        "requestParam": json.dumps(request_param),
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://puls2.pulmuone.com/src/php/menu/week.php",
    }

    try:
        response = requests.post(
            url,
            data=payload,
            headers=headers,
            timeout=30,
            verify=requests_verify(),
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        print(f"Failed to fetch menu data: {exc}")
        return None


def split_side_dishes(side_dishes):
    return [item.strip() for item in (side_dishes or "").split(",") if item.strip()]


def summarize_day_menu(raw_data):
    summary = {"lunch": "정보 없음", "dinner": "정보 없음"}
    if not raw_data or not raw_data.get("data"):
        return summary

    for item in raw_data["data"]:
        meal_type, main_dish = item[1], item[3]
        if "중식 일반메뉴" in meal_type:
            summary["lunch"] = main_dish or "정보 없음"
        elif "석식 일반메뉴" in meal_type:
            summary["dinner"] = main_dish or "정보 없음"

    return summary


def build_weekly_summary(seed_data):
    weekly_summary = []
    for index, day_info in enumerate(seed_data.get("day", [])):
        raw_date = str(day_info[2]) if len(day_info) > 2 else ""
        weekday_kr = str(day_info[1]) if len(day_info) > 1 else ""
        is_workday = str(day_info[3]) == "1" if len(day_info) > 3 else False
        if not (len(raw_date) == 8 and raw_date.isdigit() and is_workday):
            continue

        date_key = f"{raw_date[0:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
        day_raw = seed_data if index == 0 else fetch_menu_data(menu_day=index)
        day_summary = summarize_day_menu(day_raw)
        weekly_summary.append(
            {
                "date": date_key,
                "weekday": weekday_kr,
                "lunch": day_summary["lunch"],
                "dinner": day_summary["dinner"],
            }
        )

        if len(weekly_summary) == 5:
            break

    return weekly_summary


def parse_menu(raw_data):
    ref_date = get_reference_date()
    menu = {
        "date": ref_date.isoformat(),
        "is_monday": ref_date.weekday() == 0,
        "lunch_salad": "정보 없음",
        "lunch_main": ["정보 없음"],
        "dinner": ["정보 없음"],
        "weekly_summary": [],
    }

    if not raw_data or "data" not in raw_data:
        return menu

    for item in raw_data["data"]:
        meal_type, main_dish, side_dishes = item[1], item[3], item[5]
        if "중식 샐러드팩" in meal_type:
            menu["lunch_salad"] = main_dish or "정보 없음"
        elif "중식 일반메뉴" in meal_type:
            menu["lunch_main"] = [main_dish or "정보 없음", *split_side_dishes(side_dishes)]
        elif "석식 일반메뉴" in meal_type:
            menu["dinner"] = [main_dish or "정보 없음", *split_side_dishes(side_dishes)]

    if menu["is_monday"]:
        menu["weekly_summary"] = build_weekly_summary(raw_data)

    return menu


def format_bullets(items):
    normalized = [item for item in items if item] or ["정보 없음"]
    return "\n".join(f"• {item}" for item in normalized)


def weekday_emoji(weekday):
    return {
        "월": "🌿",
        "화": "🍅",
        "수": "🥗",
        "목": "🍜",
        "금": "🍱",
    }.get(weekday, "📅")


def build_section_container(title, content):
    return {
        "type": "Container",
        "style": "emphasis",
        "spacing": "Medium",
        "separator": True,
        "items": [
            {
                "type": "TextBlock",
                "text": title,
                "weight": "Bolder",
                "size": "Medium",
                "wrap": True,
            },
            content,
        ],
    }


def build_weekly_summary_block(menu):
    if not menu["weekly_summary"]:
        return {
            "type": "TextBlock",
            "text": "주간 식단 정보가 없습니다.",
            "wrap": True,
            "spacing": "Small",
        }

    items = []
    for day in menu["weekly_summary"]:
        items.append(
            {
                "type": "Container",
                "style": "accent",
                "spacing": "Medium",
                "items": [
                    {
                        "type": "ColumnSet",
                        "columns": [
                            {
                                "type": "Column",
                                "width": "auto",
                                "items": [
                                    {
                                        "type": "TextBlock",
                                        "text": weekday_emoji(day["weekday"]),
                                        "size": "Large",
                                        "spacing": "None",
                                    }
                                ],
                            },
                            {
                                "type": "Column",
                                "width": "stretch",
                                "items": [
                                    {
                                        "type": "TextBlock",
                                        "text": f"{day['date']} ({day['weekday']})",
                                        "weight": "Bolder",
                                        "wrap": True,
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "type": "FactSet",
                        "facts": [
                            {"title": "🍽 점심", "value": day["lunch"]},
                            {"title": "🌙 저녁", "value": day["dinner"]},
                        ],
                    },
                ],
            }
        )

    return {
        "type": "Container",
        "items": items,
    }


def build_today_detail_block(menu):
    return {
        "type": "Container",
        "spacing": "Small",
        "items": [
            {
                "type": "TextBlock",
                "text": "🥗 중식 샐러드",
                "weight": "Bolder",
                "wrap": True,
            },
            {
                "type": "TextBlock",
                "text": menu["lunch_salad"],
                "wrap": True,
                "spacing": "Small",
            },
            {
                "type": "TextBlock",
                "text": "🍽 중식 일반",
                "weight": "Bolder",
                "spacing": "Medium",
                "wrap": True,
            },
            {
                "type": "TextBlock",
                "text": format_bullets(menu["lunch_main"]),
                "wrap": True,
                "spacing": "Small",
            },
            {
                "type": "TextBlock",
                "text": "🌙 석식 일반",
                "weight": "Bolder",
                "spacing": "Medium",
                "wrap": True,
            },
            {
                "type": "TextBlock",
                "text": format_bullets(menu["dinner"]),
                "wrap": True,
                "spacing": "Small",
            },
        ],
    }


def build_card_body(menu):
    body = [
        {
            "type": "Container",
            "style": "good",
            "items": [
                {
                    "type": "TextBlock",
                    "text": "🍱 오늘의 식단",
                    "weight": "Bolder",
                    "size": "Large",
                    "wrap": True,
                },
                {
                    "type": "TextBlock",
                    "text": f"오늘 날짜 · {menu['date']}",
                    "spacing": "Small",
                    "isSubtle": True,
                    "wrap": True,
                },
            ],
        },
    ]

    if menu["is_monday"]:
        body.append(build_section_container("🗓 이번 주 식단 요약", build_weekly_summary_block(menu)))

    body.append(build_section_container("✨ 오늘 상세", build_today_detail_block(menu)))

    return body


def build_power_automate_card_payload(menu):
    return {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "contentUrl": None,
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.2",
                    "body": build_card_body(menu),
                },
            }
        ],
    }


def send_message(url, menu):
    payload = build_power_automate_card_payload(menu)

    try:
        response = requests.post(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=30,
            verify=requests_verify(),
        )
        return response.status_code
    except Exception as exc:
        print(f"Failed to send message: {exc}")
        return None
