import json

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
