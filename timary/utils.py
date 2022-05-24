import json

from crispy_forms.layout import HTML
from django.template import Context, Engine


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
