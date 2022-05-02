import datetime

from django import forms
from django.contrib import admin, messages
from django.core.mail import send_mail
from django.db.models import Sum
from django.template.response import TemplateResponse
from django.urls import path
from django_otp.admin import OTPAdminSite

from timary.models import Contract, DailyHoursInput, Invoice, SentInvoice, User

# Register your models here.
admin.site.register(User)
admin.site.register(Invoice)
admin.site.register(SentInvoice)
admin.site.register(DailyHoursInput)


class SendEmailForm(forms.Form):
    subject = forms.CharField(max_length=300)
    message = forms.CharField(max_length=2000, widget=forms.Textarea)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["message"].widget.attrs["rows"] = 8
        self.fields["message"].widget.attrs["cols"] = 15
        self.fields["message"].widget.attrs["textarea"] = True


def send_emails(subject, message):
    send_mail(
        subject,
        message,
        None,
        recipient_list=User.objects.all().values_list("email", flat=True),
        fail_silently=False,
    )


class TimaryAdminSite(OTPAdminSite):
    index_template = "admin/custom_index.html"

    def analytics(self, request):
        users = {
            "total": User.objects.count(),
            "starter": User.objects.filter(
                membership_tier=User.MembershipTier.STARTER
            ).count(),
            "professional": User.objects.filter(
                membership_tier=User.MembershipTier.PROFESSIONAL
            ).count(),
            "business": User.objects.filter(
                membership_tier=User.MembershipTier.BUSINESS
            ).count(),
            "invoice_fee": User.objects.filter(
                membership_tier=User.MembershipTier.INVOICE_FEE
            ).count(),
        }
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
                DailyHoursInput.objects.aggregate(total=Sum("hours"))["total"]
            ),
            "invoice_total": Invoice.objects.count(),
            "contracts_total": Contract.objects.count(),
        }
        current_date = datetime.datetime.today()
        money_stats = {
            "recurring": (users["starter"] * 5)
            + (users["professional"] * 19)
            + (users["business"] * 49),
            "fees": SentInvoice.objects.filter(
                user__membership_tier=User.MembershipTier.INVOICE_FEE,
                date_sent__month__gte=current_date.month,
                date_sent__year__gte=current_date.year,
            ).aggregate(total=Sum("total_price"))["total"]
            * 0.01,
        }
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
