from crispy_forms.layout import HTML, ButtonHolder, Column, Layout, Row


def hours_form_helper(method_type, is_mobile, hour=None):
    from django.urls import reverse

    flex_dir = "flex-col space-y-5" if is_mobile else "flex-row space-x-5"

    return {
        "get": {
            "form_id": "new-hours-form",
            "attrs": {
                "hx-post": reverse("timary:create_hours"),
                "hx-target": "#hours-list",
                "hx-swap": "afterbegin",
            },
            "form_class": "card pb-5 bg-neutral text-neutral-content",
            "layout": Layout(
                Row(
                    "hours",
                    "date_tracked",
                    "invoice",
                    css_class=f"card-body flex {flex_dir} justify-center",
                ),
                ButtonHolder(
                    HTML('<a href="#" class="btn" id="close-hours-modal">Close</a>'),
                    HTML(
                        '<button hx-trigger="enterKey, click" class="btn btn-primary" '
                        'type="submit" hx-indicator="#spinnr"> Add new hours</button>'
                    ),
                    css_class="card-actions flex justify-center",
                ),
            ),
        },
        "put": {
            "form_id": "update-hours-form",
            "attrs": {
                "hx-put": reverse("timary:update_hours", kwargs={"hours_id": hour.id}),
                "hx-target": "this",
                "hx-swap": "outerHTML",
            },
            "form_class": "card pb-5 bg-neutral text-neutral-content",
            "layout": Layout(
                Row(
                    "hours",
                    "date_tracked",
                    "invoice",
                    css_class=f"card-body flex {flex_dir} justify-center",
                ),
                ButtonHolder(
                    HTML(
                        f"""
                    <a class="btn btn-ghost" hx-get="{reverse(
            "timary:get_single_hours", kwargs={"hours_id": hour.id}
        )}" hx-target="closest form" hx-swap="outerHTML" hx-indicator="#spinnr"> Cancel </a>
                    """
                    ),
                    HTML(
                        '<button hx-trigger="enterKey, click" class="btn btn-primary" '
                        'type="submit" hx-indicator="#spinnr"> Update hours</button>'
                    ),
                    css_class="card-actions flex justify-center",
                ),
            ),
        },
    }[method_type]


def invoice_form_helper(method_type, is_mobile, invoice=None, show_cancel_button=True):
    from django.urls import reverse

    flex_dir = "card-body flex-col space-y-5" if is_mobile else "flex-row space-x-5"

    cancel_button = (
        HTML('<a href="#" class="btn" id="close-invoice-modal">Close</a>')
        if show_cancel_button
        else HTML("<span></span>")
    )

    return {
        "get": {
            "form_id": "new-invoice-form",
            "attrs": {
                "hx-post": reverse("timary:create_invoice"),
                "hx-target": "#invoices-list",
                "hx-swap": "beforeend",
            },
            "form_class": "card p-5 bg-neutral text-neutral-content",
            "layout": Layout(
                Column(
                    "title",
                    "hourly_rate",
                    "invoice_interval",
                    "email_recipient_name",
                    "email_recipient",
                ),
                ButtonHolder(
                    cancel_button,
                    HTML(
                        '<button hx-trigger="enterKey, click" class="btn btn-primary" '
                        'type="submit" hx-indicator="#spinnr"> Add new invoice</button>'
                    ),
                    css_class="card-actions flex justify-center",
                ),
            ),
        },
        "put": {
            "form_id": "update-invoice-form",
            "attrs": {
                "hx-put": reverse(
                    "timary:update_invoice", kwargs={"invoice_id": invoice.id}
                ),
                "hx-target": "this",
                "hx-swap": "outerHTML",
            },
            "form_class": "card pb-5 bg-neutral text-neutral-content",
            "layout": Layout(
                Row(
                    "title",
                    "hourly_rate",
                    "invoice_interval",
                    css_class=f"card-body flex {flex_dir} justify-center",
                ),
                Row(
                    "email_recipient_name",
                    "email_recipient",
                    css_class=f"flex {flex_dir} justify-center",
                ),
                ButtonHolder(
                    HTML(
                        f"""
                    <a class="btn btn-ghost" hx-get="{reverse(
            "timary:get_single_invoice", kwargs={"invoice_id": invoice.id}
        )}" hx-target="closest form" hx-swap="outerHTML" hx-indicator="#spinnr"> Cancel </a>
                    """
                    ),
                    HTML(
                        '<button hx-trigger="enterKey, click" class="btn btn-primary" '
                        'type="submit" hx-indicator="#spinnr"> Update invoice</button>'
                    ),
                    css_class="card-actions flex justify-center",
                ),
            ),
        },
    }[method_type]


def profile_form_helper(is_mobile):
    from django.urls import reverse

    flex_dir = "card-body flex-col space-y-5" if is_mobile else "flex-row space-x-5"

    return {
        "form_id": "update-user-profile",
        "attrs": {
            "hx-put": reverse("timary:update_user_profile"),
            "hx-target": "this",
            "hx-swap": "outerHTML",
        },
        "form_class": "card pb-5 bg-neutral text-neutral-content",
        "layout": Layout(
            Row(
                "email",
                "first_name",
                "last_name",
                css_class=f"card-body flex {flex_dir} justify-center",
            ),
            Row(
                "phone_number",
                "membership_tier",
                css_class=f"flex {flex_dir} justify-center",
            ),
            ButtonHolder(
                HTML(
                    f"""
                    <a class="btn btn-ghost" hx-get="{reverse("timary:user_profile_partial")}" hx-target="closest form"
                    hx-swap="outerHTML" hx-indicator="#spinnr"> Cancel </a>
                    """
                ),
                HTML(
                    '<button hx-trigger="enterKey, click" class="btn btn-primary" '
                    'type="submit" hx-indicator="#spinnr"> Update profile </button>'
                ),
                css_class="card-actions flex justify-center",
            ),
        ),
    }


def login_form_helper():
    return {
        "form_id": "login-form",
        "form_class": "card pb-5 bg-neutral text-neutral-content",
        "layout": Layout(
            Column(
                "email",
                "password",
                css_class="card-body flex justify-center",
            ),
            ButtonHolder(
                HTML(
                    '<button hx-trigger="enterKey, click" class="btn btn-primary" '
                    'type="submit" hx-indicator="#spinnr"> Login </button>'
                ),
                css_class="card-actions flex justify-center",
            ),
        ),
    }
