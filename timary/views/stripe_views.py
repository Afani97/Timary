import datetime
import sys
from datetime import timedelta

import stripe
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from timary.forms import PayInvoiceForm
from timary.models import SentInvoice, User
from timary.services.email_service import EmailService
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
            return JsonResponse({"valid": False, "errors": pay_invoice_form.errors})
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
            if invoicee_payment_method:
                saved_payment_method = True
                last_4_bank = invoicee_payment_method["us_bank_account"]["last4"]

        hours, total = sent_invoice.get_hours_tracked()
        context = {
            "invoice": sent_invoice.invoice,
            "sent_invoice": sent_invoice,
            "hours_tracked": hours,
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
    if "user_id" not in request.GET:
        return redirect(reverse("timary:register"))
    user = User.objects.filter(id=request.GET.get("user_id")).first()
    if not user:
        return redirect(reverse("timary:register"))

    StripeService.create_subscription(user)

    login(request, user)

    return redirect(reverse("timary:manage_invoices"))


@require_http_methods(["GET"])
@login_required()
def update_connect_account(request):
    account_url = StripeService.update_connect_account(
        request.user.id, request.user.stripe_connect_id
    )
    return redirect(account_url)


@require_http_methods(["GET"])
@login_required()
def completed_connect_account(request):
    if "user_id" not in request.GET:
        return redirect(reverse("timary:register"))
    user = User.objects.filter(id=request.GET.get("user_id")).first()
    if not user:
        return redirect(reverse("timary:register"))
    login(request, user)
    return redirect(reverse("timary:user_profile"))


@require_http_methods(["POST"])
@csrf_exempt
def stripe_webhook(request):
    """
    Test locally => stripe listen --forward-to localhost:8000/stripe-webhook/
    Copy webhook secret into STRIPE_WEBHOOK_SECRET
    """
    payload = request.body
    sig_header = request.META["HTTP_STRIPE_SIGNATURE"]

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

        if SentInvoice.objects.filter(
            stripe_payment_intent_id=payment_intent["id"]
        ).exists():
            sent_invoice = SentInvoice.objects.get(
                stripe_payment_intent_id=payment_intent["id"]
            )

            sent_invoice.paid_status = SentInvoice.PaidStatus.FAILED
            sent_invoice.save()

            hours_tracked, _ = sent_invoice.get_hours_tracked()
            today = datetime.date.today()

            # Notify client that payment failed
            msg_body = render_to_string(
                "email/sent_invoice_email.html",
                {
                    "can_accept_payments": sent_invoice.user.can_accept_payments,
                    "site_url": settings.SITE_URL,
                    "user_name": sent_invoice.user.invoice_branding_properties()[
                        "user_name"
                    ],
                    "next_weeks_date": sent_invoice.user.invoice_branding_properties()[
                        "next_weeks_date"
                    ],
                    "recipient_name": sent_invoice.invoice.email_recipient_name,
                    "total_amount": sent_invoice.total_price,
                    "sent_invoice": sent_invoice,
                    "hours_tracked": hours_tracked,
                    "tomorrows_date": today + timedelta(days=1),
                    "invoice_branding": sent_invoice.user.invoice_branding_properties(),
                },
            )
            EmailService.send_html(
                f"Unable to process {sent_invoice.invoice.user.first_name}'s invoice. "
                f"An error occurred while trying to "
                f"transfer the funds for this invoice. Please give it another try.",
                msg_body,
                sent_invoice.invoice.email_recipient,
            )
        else:
            # Other stripe webhook event
            pass

    elif event["type"] in [
        "payment_intent.succeeded",
        "charge.succeeded",
        "transfer.created",
    ]:
        # Handle a successful payment
        payment_intent = event["data"]["object"]
        if SentInvoice.objects.filter(
            stripe_payment_intent_id=payment_intent["id"]
        ).exists():
            sent_invoice = SentInvoice.objects.get(
                stripe_payment_intent_id=payment_intent["id"]
            )
            if sent_invoice.paid_status == SentInvoice.PaidStatus.PAID:
                return JsonResponse({"success": True})

            sent_invoice.paid_status = SentInvoice.PaidStatus.PAID
            sent_invoice.date_sent = datetime.date.today()
            sent_invoice.save()
            sent_invoice.success_notification()
        else:
            # Other stripe webhook event
            pass
    elif event["type"] == "account.updated":
        user_account_id = event["data"]["object"]["id"]
        user = User.objects.filter(stripe_connect_id=user_account_id)
        if user.exists():
            user = user.first()
            account_connect_requirements_reason = event["data"]["object"][
                "requirements"
            ]["disabled_reason"]
            user.update_payouts_enabled(account_connect_requirements_reason)
    # ... handle other event types
    else:
        print("Unhandled event type {}".format(event["type"]))

    return JsonResponse({"success": True})
