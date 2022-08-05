import uuid

from crispy_forms.layout import HTML, ButtonHolder, Column, Layout, Row


def hours_form_helper(method_type, is_mobile, hour=None, invoice_id=None):
    from django.urls import reverse

    flex_dir = "flex-col space-y-5" if is_mobile else "flex-row space-x-5"

    desktop_rows = Row(
        "hours",
        "date_tracked",
        "invoice",
        css_class=f"card-body flex {flex_dir} justify-center space-x-5",
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
                "hx-swap": "outerHTML",
            },
            "form_class": "card bg-neutral text-neutral-content",
            "layout": Layout(
                rows,
                ButtonHolder(
                    HTML(
                        """
                        <a href="#" class="btn" id="close-hours-modal" _="on click call clearHoursModal()">Close</a>
                        """
                    ),
                    HTML(
                        """<button hx-trigger="enterKey, click" class="btn btn-primary submit-btn"
                        type="submit"> Add new hours</button>"""
                    ),
                    css_class="card-actions mb-5 flex justify-center",
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
                    css_class="card-body flex flex-col space-y-5 justify-center",
                ),
                ButtonHolder(
                    HTML(
                        f"""
                    <a class="btn btn-ghost" hx-get="{reverse(
            "timary:get_single_hours", kwargs={"hours_id": hour.id}
        )}" hx-target="closest form" hx-swap="outerHTML" _="on click add .loading to me"> Cancel </a>
                    """
                    ),
                    HTML(
                        """<button hx-trigger="enterKey, click" class="btn btn-primary submit-btn"
                        type="submit"> Update hours</button>"""
                    ),
                    css_class="card-actions flex justify-center",
                ),
            ),
        },
        "patch": {
            "form_id": f"update-hours-form-{str(uuid.uuid4())}",
            "attrs": {
                "hx-patch": reverse("timary:patch_hours", kwargs={"hours_id": hour.id}),
                "hx-target": "this",
                "hx-swap": "outerHTML",
                "hx-vals": f'{{ "invoice": "{str(invoice_id)}" }}',
            },
            "form_class": "card pb-5 bg-neutral text-neutral-content -mx-4",
            "layout": Layout(
                Row(
                    "hours",
                    "date_tracked",
                    HTML(
                        """<button hx-trigger="enterKey, click" class="btn btn-primary btn-sm mt-7 submit-btn"
                        type="submit">Update</button>"""
                    ),
                    HTML(
                        f"""
                        <button class="btn btn-error btn-sm btn-circle mt-7" hx-delete="{reverse(
            "timary:delete_hours", kwargs={"hours_id": hour.id}
        )}" hx-swap="outerHTML" hx-target="closest form">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24"
                            stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                            d="M6 18L18 6M6 6l12 12" /></svg>
                        </button>
                        """
                    ),
                    css_class="flex flex-row justify-evenly content-center",
                )
            ),
        },
    }[method_type]


def invoice_form_helper(method_type, is_mobile, invoice=None, show_cancel_button=True):
    from django.urls import reverse

    flex_dir = "card-body flex-col space-y-5" if is_mobile else "flex-row space-x-5"

    cancel_button = (
        HTML(
            """
            <a href="#" class="btn" id="close-invoice-modal" _="on click call clearInvoiceModal()">Close</a>
            """
        )
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
            "form_class": "card px-5 bg-neutral text-neutral-content",
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
                        """<button hx-trigger="enterKey, click" class="btn btn-primary submit-btn"
                        type="submit"> Add new invoice</button>"""
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
                Column(
                    Row(
                        "title",
                        "hourly_rate",
                        "invoice_interval",
                        "total_budget",
                        css_class=f"flex {flex_dir} justify-center",
                    ),
                    Row(
                        "email_recipient_name",
                        "email_recipient",
                        css_class=f"flex {flex_dir} justify-center",
                    ),
                    css_class="card-body space-y-5",
                ),
                ButtonHolder(
                    HTML(
                        f"""
                <a class="btn btn-ghost" hx-get="{reverse(
                    "timary:get_single_invoice", kwargs={"invoice_id": invoice.id}
                )}" hx-target="closest form" hx-swap="outerHTML" _="on click add .loading to me"> Cancel </a>
                """
                    ),
                    HTML(
                        """<button hx-trigger="enterKey, click" class="btn btn-primary submit-btn"
                        type="submit"> Update invoice</button>"""
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
            "hx-post": reverse("timary:update_user_profile"),
            "hx-target": "this",
            "hx-swap": "outerHTML",
            "hx-encoding": "multipart/form-data",
        },
        "form_class": "card pb-5 bg-neutral text-neutral-content",
        "layout": Layout(
            Row(
                "profile_pic",
                css_class=f"card-body flex {flex_dir} justify-center",
            ),
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
                    hx-swap="outerHTML" _="on click add .loading to me"> Cancel </a>
                    """
                ),
                HTML(
                    """<button hx-trigger="enterKey, click" class="btn btn-primary submit-btn"
                    type="submit"> Update profile </button>"""
                ),
                css_class="card-actions flex justify-center mt-8",
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
                Column(
                    "password",
                    HTML(
                        """
                        <a href="{% url "password_reset" %}" class="link">Forgot password?</a>
                        """
                    ),
                    css_class="flex flex-col space-y-2",
                ),
                css_class="card-body flex flex-col justify-center",
            ),
            ButtonHolder(
                HTML(
                    """<button hx-trigger="enterKey, click" class="btn btn-primary"
                    type="submit"> Login </button>"""
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
                    """<div class="form-control">
                    <label class="label"><span class="label-text">Debit card</span> </label>
                    <div id="card-element"></div>
                    <label class="label">
                    <span class="label-text-alt">Stripe requires a debit card to process your invoices into your
                    bank account.</span>
                    </label>
                    </div>
                    """,
                ),
                css_class="card-body flex justify-center",
            ),
            ButtonHolder(
                HTML(
                    """<button class="btn btn-primary" id="submit-form"
                    type="submit"> Continue </button>"""
                ),
                css_class="card-actions flex justify-center",
            ),
        ),
    }
