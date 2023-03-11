from django import forms
from django.contrib import admin, messages
from django.db.models import Sum
from django.template.response import TemplateResponse
from django.urls import path
from django_otp.admin import OTPAdminSite

from timary.invoice_builder import InvoiceBuilder
from timary.models import (
    Contract,
    HoursLineItem,
    IntervalInvoice,
    Invoice,
    MilestoneInvoice,
    SentInvoice,
    SingleInvoice,
    User,
    WeeklyInvoice,
)

# Register your models here.
from timary.services.email_service import EmailService


@admin.action(description="Pause selected invoices")
def pause_invoices(modeladmin, request, queryset):
    updated = queryset.update(is_paused=True)
    modeladmin.message_user(
        request,
        f"{updated} invoices were paused",
        messages.SUCCESS,
    )


@admin.action(description="Unpause selected invoices")
def unpause_invoices(modeladmin, request, queryset):
    updated = queryset.update(is_paused=False)
    modeladmin.message_user(
        request,
        f"{updated} invoices were unpaused",
        messages.SUCCESS,
    )


@admin.action(description="Archive selected invoices")
def archive_invoices(modeladmin, request, queryset):
    updated = queryset.update(is_archived=True)
    modeladmin.message_user(
        request,
        f"{updated} invoices were archived",
        messages.SUCCESS,
    )


@admin.action(description="Unarchive selected invoices")
def unarchive_invoices(modeladmin, request, queryset):
    updated = queryset.update(is_archived=False)
    modeladmin.message_user(
        request,
        f"{updated} invoices were unarchived",
        messages.SUCCESS,
    )


class InvoiceAdminMixin:
    list_display = ["title"]
    actions = [pause_invoices, unpause_invoices, archive_invoices, unarchive_invoices]


class IntervalInvoiceAdmin(InvoiceAdminMixin, admin.ModelAdmin):
    pass


class MilestoneInvoiceAdmin(InvoiceAdminMixin, admin.ModelAdmin):
    pass


class WeeklyInvoiceAdmin(InvoiceAdminMixin, admin.ModelAdmin):
    pass


def resend_invoice(sent_invoice):
    if sent_invoice.paid_status == SentInvoice.PaidStatus.PAID:
        return False
    if not sent_invoice.user.settings["subscription_active"]:
        return False
    invoice = sent_invoice.invoice

    if (
        isinstance(sent_invoice.invoice, SingleInvoice)
        and sent_invoice.invoice.installments > 1
    ):
        sent_invoice.update_installments()

    from datetime import date

    month_sent = date.strftime(sent_invoice.date_sent, "%m/%Y")
    msg_body = InvoiceBuilder(invoice.user).send_invoice(
        {
            "sent_invoice": sent_invoice,
            "line_items": sent_invoice.get_rendered_line_items(),
        }
    )
    msg_subject = (
        f"{invoice.title}'s Invoice from {invoice.user.first_name} for {month_sent}"
    )
    EmailService.send_html(
        msg_subject,
        msg_body,
        invoice.client.email,
    )
    sent_invoice.send_sms_message(msg_subject)
    return True


class SentInvoiceAdmin(admin.ModelAdmin):
    actions = ["resend_sent_invoice", "cancel_sent_invoice"]

    @admin.action(description="Resend selected sent invoices")
    def resend_sent_invoice(self, request, queryset):
        sent_ctn = 0
        for invoice in queryset:
            invoice_sent = resend_invoice(invoice)
            if invoice_sent:
                sent_ctn += 1

        self.message_user(
            request,
            f"{sent_ctn} sent invoices have been resent",
            messages.SUCCESS,
        )

    @admin.action(description="Cancel selected sent invoices")
    def cancel_sent_invoice(self, request, queryset):
        updated = queryset.update(paid_status=SentInvoice.PaidStatus.CANCELLED)
        self.message_user(
            request,
            f"{updated} sent invoices were cancelled",
            messages.SUCCESS,
        )


class HoursLineItemAdmin(admin.ModelAdmin):
    actions = ["cancel_recurring_hours"]
    ordering = ["-created_at"]

    @admin.action(description="Cancel recurring schedule for selected hour line items")
    def cancel_recurring_hours(self, request, queryset):
        updated = queryset.update(recurring_logic=None)

        self.message_user(
            request,
            f"{updated} recurring line items were cancelled",
            messages.SUCCESS,
        )


class UserAdmin(admin.ModelAdmin):
    list_display = [
        "first_name",
        "last_name",
        "email",
        "stripe_subscription_status",
        "stripe_payouts_enabled",
        "accounting_org",
    ]
    actions = ["cancel_subscriptions", "re_add_subscriptions"]

    @admin.action(description="Cancel subscription for selected users")
    def cancel_subscriptions(self, request, queryset):
        updated = 0
        for user in queryset:
            from timary.services.stripe_service import StripeService

            subscription_cancelled = StripeService.cancel_subscription(user)
            if subscription_cancelled:
                updated += 1

        self.message_user(
            request,
            f"{updated} users have cancelled their subscriptions",
            messages.SUCCESS,
        )

    @admin.action(description="Re-add subscriptions for selected users")
    def re_add_subscriptions(self, request, queryset):
        updated = 0
        for user in queryset:
            from timary.services.stripe_service import StripeService

            subscription_created = StripeService.readd_subscription(user)
            if subscription_created:
                updated += 1

        if updated > 0:
            self.message_user(
                request,
                f"{updated} users have re-added their subscriptions",
                messages.SUCCESS,
            )
        else:
            self.message_user(
                request,
                f"{queryset.count() - updated} users could not re-add their subscriptions",
            )


admin.site.register(User, UserAdmin)
admin.site.register(IntervalInvoice, IntervalInvoiceAdmin)
admin.site.register(MilestoneInvoice, MilestoneInvoiceAdmin)
admin.site.register(WeeklyInvoice, WeeklyInvoiceAdmin)
admin.site.register(SingleInvoice)
admin.site.register(SentInvoice, SentInvoiceAdmin)
admin.site.register(HoursLineItem, HoursLineItemAdmin)


class SendEmailForm(forms.Form):
    subject = forms.CharField(
        max_length=300,
        widget=forms.Textarea(
            attrs={
                "rows": 1,
                "class": "textarea textarea-bordered border-2 text-lg w-full",
            }
        ),
    )
    message = forms.CharField(
        max_length=2000,
        widget=forms.Textarea(
            attrs={
                "rows": 8,
                "cols": 15,
                "class": "textarea textarea-bordered border-2 text-lg w-full",
            }
        ),
    )


def send_emails(subject, message):
    EmailService.send_plain(
        subject, message, User.objects.all().values_list("email", flat=True)
    )


class TimaryAdminSite(OTPAdminSite):
    index_template = "admin/custom_index.html"

    def analytics(self, request):
        users = {
            "total": int(User.objects.exclude(stripe_subscription_status=3).count())
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
                HoursLineItem.objects.aggregate(total=Sum("quantity"))["total"]
            ),
            "invoice_total": Invoice.objects.count(),
            "contracts_total": Contract.objects.count(),
        }
        money_stats = {
            "recurring": int(users["total"]) * 29,
        }
        money_stats["mrr_goal"] = (money_stats["recurring"]) / 10_000
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
