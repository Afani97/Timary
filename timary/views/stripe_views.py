from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from twilio.rest import Client

from timary.forms import PayInvoiceForm
from timary.models import SentInvoice
from timary.services.stripe_service import StripeService


@require_http_methods(["GET", "POST"])
@csrf_exempt
def pay_invoice(request, sent_invoice_id):
    sent_invoice = get_object_or_404(SentInvoice, id=sent_invoice_id)
    if sent_invoice.paid_status == SentInvoice.PaidStatus.PAID:
        return redirect(reverse("timary:login"))

    if request.method == "POST":
        pay_invoice_form = PayInvoiceForm(request.POST, sent_invoice=sent_invoice)
        if pay_invoice_form.is_valid():
            return JsonResponse({"valid": True, "errors": {}})
        else:
            return JsonResponse(
                {"valid": False, "errors": pay_invoice_form.errors.as_json()}
            )
    else:
        client_secret = StripeService.create_payment_intent_for_payout(sent_invoice)

        context = {
            "invoice": sent_invoice.invoice,
            "sent_invoice": sent_invoice,
            "hours_tracked": sent_invoice.get_hours_tracked(),
            "pay_invoice_form": PayInvoiceForm(),
            "stripe_public_key": StripeService.stripe_public_api_key,
            "client_secret": client_secret,
            "return_url": request.build_absolute_uri(
                reverse(
                    "timary:invoice_payment_success",
                    kwargs={"sent_invoice_id": sent_invoice.id},
                )
            ),
        }
        return render(request, "invoices/pay_invoice.html", context)


@require_http_methods(["GET"])
def invoice_payment_success(request, sent_invoice_id):
    sent_invoice = get_object_or_404(SentInvoice, id=sent_invoice_id)
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


@require_http_methods(["GET"])
@login_required()
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


@require_http_methods(["GET"])
@login_required()
def update_connect_account(request):
    account_url = StripeService.update_connect_account(request.user.stripe_connect_id)
    return redirect(account_url)


@require_http_methods(["GET"])
@login_required()
def completed_connect_account(request):
    connect_account = StripeService.get_connect_account(request.user.stripe_connect_id)
    request.user.stripe_payouts_enabled = connect_account["payouts_enabled"]
    request.user.save()
    return redirect(reverse("timary:user_profile"))
