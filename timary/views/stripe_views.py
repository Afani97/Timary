from django.conf import settings
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from twilio.rest import Client

from timary.models import SentInvoice
from timary.services.stripe_service import StripeService


def invoice_payment_success(request, invoice_id):
    sent_invoice = get_object_or_404(SentInvoice, id=invoice_id)
    if sent_invoice.paid_status == SentInvoice.PaidStatus.PAID:
        return redirect(reverse("timary:login"))
    sent_invoice.paid_status = SentInvoice.PaidStatus.PAID
    sent_invoice.save()
    if sent_invoice.invoice.user.phone_number:
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        _ = client.messages.create(
            to=sent_invoice.invoice.user.formatted_phone_number,
            from_=settings.TWILIO_PHONE_NUMBER,
            body=f"Invoice for {sent_invoice.invoice.title} has been paid! "
            f"You should see {sent_invoice.total_price} deposited into your bank account shortly",
        )
    return render(request, "invoices/success_pay_invoice.html", {})


def onboard_success(request):
    success = StripeService.create_subscription(request.user)
    if success:
        connect_account = StripeService.get_connect_account(
            request.user.stripe_connect_id
        )
        request.user.stripe_payouts_enabled = connect_account["payouts_enabled"]
        request.user.save()
        return redirect(reverse("timary:manage_invoices"))
    else:
        # TODO: Redirect to error page to error missing details
        return redirect(reverse("timary:index"))


def update_connect_account(request):
    account_url = StripeService.update_connect_account(request.user.stripe_connect_id)
    return redirect(account_url)


def completed_connect_account(request):
    connect_account = StripeService.get_connect_account(request.user.stripe_connect_id)
    request.user.stripe_payouts_enabled = connect_account["payouts_enabled"]
    request.user.save()
    return redirect(reverse("timary:user_profile"))
