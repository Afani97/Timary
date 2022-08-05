import json

from crispy_forms.layout import HTML
from django.template import Context, Engine
from pyquery import PyQuery as pq


def render_form_errors(form):
    template = Engine(
        app_dirs=True,
    ).get_template("partials/_form_errors.html")
    context = Context({"form_errors": json.loads(form.errors.as_json())})
    form_errors = template.render(context)
    return HTML(form_errors)


def render_form_messages(messages):
    template = Engine(
        app_dirs=True,
    ).get_template("partials/_form_success.html")
    context = Context({"form_msg": messages})
    form_messages = template.render(context)
    return HTML(form_messages)


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


def add_loader(form):
    d = pq(form)
    d("form").attr[
        "_"
    ] = "on submit add .loading to .submit-btn end on htmx:afterRequest remove .loading from .submit-btn"
    return str(d)
