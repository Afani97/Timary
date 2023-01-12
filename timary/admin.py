import datetime

from django import forms
from django.contrib import admin, messages
from django.db.models import Sum
from django.template.response import TemplateResponse
from django.urls import path
from django_otp.admin import OTPAdminSite

from timary.models import Contract, HoursLineItem, Invoice, SentInvoice, User

# Register your models here.
from timary.services.email_service import EmailService

admin.site.register(User)
admin.site.register(Invoice)
admin.site.register(SentInvoice)
admin.site.register(HoursLineItem)


class SendEmailForm(forms.Form):
    subject = forms.CharField(max_length=300)
    message = forms.CharField(max_length=2000, widget=forms.Textarea)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["message"].widget.attrs["rows"] = 8
        self.fields["message"].widget.attrs["cols"] = 15
        self.fields["message"].widget.attrs["textarea"] = True


def send_emails(subject, message):
    EmailService.send_plain(
        subject, message, User.objects.all().values_list("email", flat=True)
    )


class TimaryAdminSite(OTPAdminSite):
    index_template = "admin/custom_index.html"

    def analytics(self, request):
        users = {"total": User.objects.count()}
        sent_invoices = {
            "total": SentInvoice.objects.count(),
            "pending": SentInvoice.objects.filter(
                paid_status=SentInvoice.PaidStatus.PENDING
            ).count(),
            "paid": SentInvoice.objects.filter(
                paid_status=SentInvoice.PaidStatus.PAID
            ).count(),
            "failed": SentInvoice.objects.filter(
                paid_status=SentInvoice.PaidStatus.FAILED
            ).count(),
        }
        overall_stats = {
            "hour_total": int(
                HoursLineItem.objects.aggregate(total=Sum("quantity"))["total"]
            ),
            "invoice_total": Invoice.objects.count(),
            "contracts_total": Contract.objects.count(),
        }
        current_date = datetime.datetime.today()
        sent_invoice_fees = SentInvoice.objects.filter(
            date_sent__month__gte=current_date.month,
            date_sent__year__gte=current_date.year,
        ).aggregate(total=Sum("total_price"))
        money_stats = {
            "recurring": int(users["total"]) * 29,
        }
        if sent_invoice_fees["total"] is not None:
            money_stats["fees"] = sent_invoice_fees["total"] * 0.01
        else:
            money_stats["fees"] = 0
        money_stats["mrr_goal"] = (
            money_stats["recurring"] + money_stats["fees"]
        ) / 10_000
        context = {
            "text": "Hello World",
            "users": users,
            "sent_invoices": sent_invoices,
            "overall_stats": overall_stats,
            "money_stats": money_stats,
            "page_name": "Custom Page",
            "app_list": self.get_app_list(request),
            **self.each_context(request),
        }
        return TemplateResponse(request, "admin/analytics.html", context)

    def send_email(self, request):
        context = {
            "text": "Send Email",
            "form": SendEmailForm(),
            "page_name": "Send Email",
            "app_list": self.get_app_list(request),
            **self.each_context(request),
        }
        if request.method == "POST":
            form = SendEmailForm(request.POST)
            if form.is_valid():
                subject = form.cleaned_data.get("subject")
                message = form.cleaned_data.get("message")
                send_emails(subject, message)
                messages.add_message(
                    request, messages.INFO, "Successfully sent out emails."
                )
        return TemplateResponse(request, "admin/send_email.html", context)

    def get_urls(self):
        return [
            path(
                "analytics/",
                self.admin_view(self.analytics),
                name="analytics",
            ),
            path(
                "send_email/",
                self.admin_view(self.send_email),
                name="send_email",
            ),
        ] + super().get_urls()
