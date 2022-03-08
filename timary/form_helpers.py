from crispy_forms.layout import HTML, ButtonHolder, Column, Layout, Row


def hours_form_helper(method_type, is_mobile, hour=None):
    from django.urls import reverse

    flex_dir = "flex-col space-y-5" if is_mobile else "flex-row space-x-5"

    desktop_rows = Row(
        "hours",
        "date_tracked",
        "invoice",
        css_class=f"card-body flex {flex_dir} justify-center space-x-5 my-5",
    )
    mobile_rows = Column(
        Row(
            "hours",
            "date_tracked",
            css_class="flex flex-row justify-center space-x-5 my-5",
        ),
        Row(
            "invoice",
            css_class="flex justify-center mb-5",
        ),
    )
    rows = mobile_rows if is_mobile else desktop_rows

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
                rows,
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
                    css_class="flex flex-col space-y-2",
                ),
                ButtonHolder(
                    cancel_button,
                    HTML(
                        '<button hx-trigger="enterKey, click" class="btn btn-primary" '
                        'type="submit" hx-indicator="#spinnr"> Add new invoice</button>'
                    ),
                    css_class="card-actions flex mt-4 justify-center",
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
                    css_class="card-actions flex justify-center mt-4",
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
                "first_name",
                "last_name",
                css_class=f"card-body flex {flex_dir} justify-center",
            ),
            Row(
                "email",
                "phone_number",
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
                css_class="card-actions flex justify-center mt-4",
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


def register_form_helper():
    return {
        "form_id": "register-form",
        "form_class": "card pb-5 bg-neutral text-neutral-content",
        "layout": Layout(
            Column(
                "full_name",
                "email",
                "password",
                "membership_tier",
                HTML(
                    '<div class="form-control"> '
                    '<label class="label"><span class="label-text">Debit card</span> </label>'
                    '<div id="card-element"></div>'
                    '<label class="label">'
                    '<span class="label-text-alt">Stripe requires a debit card to process your invoices into your '
                    "bank account.</span>"
                    "</label>"
                    "</div>",
                ),
                css_class="card-body flex justify-center",
            ),
            ButtonHolder(
                HTML(
                    '<button class="btn btn-primary" id="submit-form"'
                    'type="submit" hx-indicator="#spinnr"> Continue </button>'
                ),
                css_class="card-actions flex justify-center",
            ),
        ),
    }
