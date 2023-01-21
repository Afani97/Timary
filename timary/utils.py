import json
import zoneinfo
from datetime import datetime, timedelta

from django.utils import timezone
from requests import Response


def show_alert_message(
    response, alert_type, message, other_trigger=None, persist=False
):
    response["HX-Trigger"] = json.dumps(
        {
            other_trigger: None,
            "showMessage": {
                "alertType": f"alert-{alert_type}",
                "message": message,
                "persist": persist,
            },
        }
    )


def show_active_timer(user):
    context = {}
    if user.timer_is_active:
        active_timer_ms, timer_paused = user.timer_is_active.split(",")
        context["active_timer_ms"] = active_timer_ms
        context["timer_paused"] = timer_paused
    return context


def simulate_requests_response(status_code, error_num, message):
    failed_response = Response()
    failed_response.code = status_code
    failed_response.error_type = "expired"
    failed_response.status_code = status_code
    response_content = {"error": error_num, "message": message}
    failed_response._content = json.dumps(response_content, indent=2).encode("utf-8")
    return failed_response


def convert_hours_to_decimal_hours(time):
    convert_hours_map = [1, 1.0 / 60, 1.0 / 3600]
    try:
        dec_time = sum(
            a * b for a, b in zip(convert_hours_map, map(int, time.split(":")))
        )
    except Exception as e:
        raise e
    if not dec_time:
        raise ValueError()
    return dec_time


def get_starting_week_from_date(date):
    if date.weekday() == 6:
        return date
    return date - timezone.timedelta(days=timezone.now().isoweekday() % 7)


def get_date_parsed(date):
    return datetime.strftime(date, "%a").lower()


def get_users_localtime(user):
    return timezone.now().astimezone(tz=zoneinfo.ZoneInfo(user.timezone))
