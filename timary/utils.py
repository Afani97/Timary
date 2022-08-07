import json


def show_alert_message(response, alert_type, message, other_trigger=None):
    response["HX-Trigger"] = json.dumps(
        {
            other_trigger: None,
            "showMessage": {
                "alertType": f"alert-{alert_type}",
                "message": message,
            },
        }
    )
