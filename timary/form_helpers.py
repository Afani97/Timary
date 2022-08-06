from crispy_forms.layout import HTML, ButtonHolder, Column, Layout, Row


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
