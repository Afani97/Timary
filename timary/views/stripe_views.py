import sys
from datetime import timedelta

import stripe
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.timezone import localtime, now
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from timary.forms import PayInvoiceForm
from timary.models import SentInvoice, User
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
        intent = StripeService.create_payment_intent_for_payout(sent_invoice)
        sent_invoice.stripe_payment_intent_id = intent["id"]
        sent_invoice.save()

        saved_payment_method = False
        last_4_bank = ""
        if sent_invoice.invoice.email_recipient_stripe_customer_id:
            invoicee_payment_method = StripeService.retrieve_customer_payment_method(
                sent_invoice.invoice.email_recipient_stripe_customer_id
            )
            # TODO: Add tests
            if invoicee_payment_method:
                saved_payment_method = True
                last_4_bank = invoicee_payment_method["us_bank_account"]["last4"]

        context = {
            "invoice": sent_invoice.invoice,
            "sent_invoice": sent_invoice,
            "hours_tracked": sent_invoice.get_hours_tracked(),
            "pay_invoice_form": PayInvoiceForm(),
            "stripe_public_key": StripeService.stripe_public_api_key,
            "client_secret": intent["client_secret"],
            "saved_payment_method": saved_payment_method,
            "last_4_bank": last_4_bank,
            "return_url": request.build_absolute_uri(
                reverse(
                    "timary:invoice_payment_success",
                    kwargs={"sent_invoice_id": sent_invoice.id},
                )
            ),
        }
        return render(request, "invoices/pay_invoice.html", context)


@require_http_methods(["GET"])
def quick_pay_invoice(request, sent_invoice_id):
    sent_invoice = get_object_or_404(SentInvoice, id=sent_invoice_id)
    if sent_invoice.paid_status == SentInvoice.PaidStatus.PAID:
        return redirect(reverse("timary:login"))

    try:
        intent = StripeService.confirm_payment(sent_invoice)
    except stripe.error.InvalidRequestError as e:
        intent = None
        print(str(e), file=sys.stderr)
    if intent:
        sent_invoice.stripe_payment_intent_id = intent["id"]
        sent_invoice.save()
        return JsonResponse(
            {
                "return_url": request.build_absolute_uri(
                    reverse(
                        "timary:invoice_payment_success",
                        kwargs={"sent_invoice_id": sent_invoice.id},
                    )
                )
            }
        )
    else:
        return JsonResponse({"error": "Unable to process payment"})


@require_http_methods(["GET"])
def invoice_payment_success(request, sent_invoice_id):
    sent_invoice = get_object_or_404(SentInvoice, id=sent_invoice_id)
    if sent_invoice.paid_status == SentInvoice.PaidStatus.PAID:
        return redirect(reverse("timary:login"))

    return render(request, "invoices/success_pay_invoice.html", {})


@require_http_methods(["GET"])
@login_required()
def onboard_success(request):
    if request.user.membership_tier != User.MembershipTier.INVOICE_FEE:
        StripeService.create_subscription(request.user)

    connect_account = StripeService.get_connect_account(request.user.stripe_connect_id)
    request.user.stripe_payouts_enabled = connect_account["payouts_enabled"]
    request.user.save()
    return redirect(reverse("timary:manage_invoices"))


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


@require_http_methods(["POST"])
@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.headers["STRIPE_SIGNATURE"]

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        # Invalid payload
        raise e
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        raise e

    # Handle the event
    if event["type"] == "payment_intent.payment_failed":
        payment_intent = event["data"]["object"]

        sent_invoice = get_object_or_404(
            SentInvoice, stripe_payment_intent_id=payment_intent["id"]
        )
        sent_invoice.paid_status = SentInvoice.PaidStatus.FAILED
        sent_invoice.save()

        hours_tracked = sent_invoice.get_hours_tracked()
        today = localtime(now()).date()

        # Notify email recipient that payment failed
        msg_body = render_to_string(
            "email/styled_email.html",
            {
                "can_accept_payments": sent_invoice.user.can_accept_payments,
                "site_url": settings.SITE_URL,
                "user_name": sent_invoice.user.first_name,
                "next_weeks_date": today + timedelta(weeks=1),
                "recipient_name": sent_invoice.invoice.email_recipient_name,
                "total_amount": sent_invoice.total_price,
                "sent_invoice_id": sent_invoice.id,
                "invoice": sent_invoice.invoice,
                "hours_tracked": hours_tracked,
                "tomorrows_date": today + timedelta(days=1),
            },
        )
        send_mail(
            f"Unable to process {sent_invoice.invoice.user.first_name}'s invoice. An error occurred while trying to "
            f"transfer the funds for this invoice. Please give it another try.",
            "",
            None,
            recipient_list=[sent_invoice.invoice.email_recipient],
            fail_silently=False,
            html_message=msg_body,
        )

    elif event["type"] == "payment_intent.succeeded":
        # Handle a successful payment
        payment_intent = event["data"]["object"]
        sent_invoice = get_object_or_404(
            SentInvoice, stripe_payment_intent_id=payment_intent["id"]
        )
        if sent_invoice.paid_status == SentInvoice.PaidStatus.PAID:
            return JsonResponse({"success": True})

        sent_invoice.paid_status = SentInvoice.PaidStatus.PAID
        sent_invoice.save()
        sent_invoice.success_notification()

    # ... handle other event types
    else:
        print("Unhandled event type {}".format(event["type"]))

    return JsonResponse({"success": True})
