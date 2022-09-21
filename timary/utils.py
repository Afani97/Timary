import json

from django.shortcuts import render


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


def render_xml(r, t, c=None):
    return render(
        r,
        f"mobile/{t}",
        context=c,
        content_type="application/xml",
    )
