from datetime import date, timedelta

from django.conf import settings
from django.template.loader import render_to_string


class InvoiceBuilder:
    def __init__(self, user):
        self.user = user

    def build_invoice(self, template, ctx):
        invoice_ctx = {
            "site_url": settings.SITE_URL,
            "user_name": self.user.invoice_branding_properties().get("user_name"),
            "invoice_branding": self.user.invoice_branding_properties(),
            "due_date": self.user.invoice_branding_properties()["next_weeks_date"],
        }
        invoice_ctx.update(**ctx)
        return render_to_string(
            f"email/{template}.html",
            invoice_ctx,
        )

    def send_invoice(self, ctx):
        return self.build_invoice(
            "sent_invoice",
            ctx,
        )

    def send_invoice_preview(self, ctx):
        return self.build_invoice("invoice_preview", ctx)

    def send_invoice_receipt(self, ctx):
        return self.build_invoice("receipt_invoice", ctx)

    def send_invoice_download_copy(self, ctx):
        return self.build_invoice("download_sent_invoice", ctx)

    def send_invoice_update(self, ctx):
        today = date.today()
        ctx.update(
            {
                "tomorrows_date": today + timedelta(days=1),
            }
        )
        return self.build_invoice("weekly_update", ctx)
