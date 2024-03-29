import sys

import stripe
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from timary.forms import PayInvoiceForm
from timary.invoice_builder import InvoiceBuilder
from timary.models import SentInvoice, SingleInvoice, User
from timary.services.email_service import EmailService
from timary.services.stripe_service import StripeService


@require_http_methods(["GET", "POST"])
@csrf_exempt
def pay_invoice(request, sent_invoice_id):
    sent_invoice = get_object_or_404(SentInvoice, id=sent_invoice_id)
    if not sent_invoice.user.settings["subscription_active"]:
        return redirect(reverse("timary:landing_page"))
    if (
        sent_invoice.paid_status == SentInvoice.PaidStatus.PAID
        or sent_invoice.paid_status == SentInvoice.PaidStatus.PENDING
        or sent_invoice.paid_status == SentInvoice.PaidStatus.CANCELLED
    ):
        return redirect(reverse("timary:landing_page"))

    if request.method == "POST":
        pay_invoice_form = PayInvoiceForm(request.POST, sent_invoice=sent_invoice)
        if pay_invoice_form.is_valid():
            return JsonResponse({"valid": True, "errors": {}})
        else:
            return JsonResponse({"valid": False, "errors": pay_invoice_form.errors})
    else:
        if isinstance(sent_invoice.invoice, SingleInvoice):
            if sent_invoice.invoice.installments == 1:
                sent_invoice.invoice.update()
                sent_invoice.total_price = sent_invoice.invoice.balance_due
            elif sent_invoice.invoice.installments > 1:
                sent_invoice.update_installments()
            sent_invoice.save()
        try:
            intent = StripeService.create_payment_intent_for_payout(sent_invoice)
        except stripe.error.InvalidRequestError as e:
            intent = None
            print(str(e), file=sys.stderr)
        if not intent:
            return redirect(reverse("timary:login"))
        sent_invoice.stripe_payment_intent_id = intent["id"]
        sent_invoice.save()

        saved_payment_method = False
        last_4_bank = ""
        if sent_invoice.invoice.client.stripe_customer_id:
            invoicee_payment_method = StripeService.retrieve_customer_payment_method(
                sent_invoice.invoice.client.stripe_customer_id
            )
            if invoicee_payment_method:
                saved_payment_method = True
                last_4_bank = invoicee_payment_method["us_bank_account"]["last4"]

        context = {
            "sent_invoice": sent_invoice,
            "line_items": sent_invoice.get_rendered_line_items(),
            "user_name": sent_invoice.user.invoice_branding_properties()["user_name"],
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


@require_http_methods(["GET", "POST"])
@csrf_exempt
def pay_invoice_email(request, email_id):
    sent_invoice = get_object_or_404(SentInvoice, email_id=email_id)
    if not sent_invoice.user.settings["subscription_active"]:
        return redirect(reverse("timary:landing_page"))
    if (
        sent_invoice.paid_status == SentInvoice.PaidStatus.PAID
        or sent_invoice.paid_status == SentInvoice.PaidStatus.PENDING
        or sent_invoice.paid_status == SentInvoice.PaidStatus.CANCELLED
    ):
        return redirect(reverse("timary:landing_page"))
    return pay_invoice(request, sent_invoice.id)


@require_http_methods(["GET"])
def quick_pay_invoice(request, sent_invoice_id):
    sent_invoice = get_object_or_404(SentInvoice, id=sent_invoice_id)
    if not sent_invoice.user.settings["subscription_active"]:
        return redirect(reverse("timary:landing_page"))
    if sent_invoice.paid_status == SentInvoice.PaidStatus.PAID:
        return redirect(reverse("timary:landing_page"))

    try:
        intent = StripeService.confirm_payment(sent_invoice)
    except stripe.error.InvalidRequestError as e:
        intent = None
        print(str(e), file=sys.stderr)

    if not intent:
        return JsonResponse({"error": "Unable to process payment"})

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


@require_http_methods(["GET"])
def invoice_payment_success(request, sent_invoice_id):
    sent_invoice = get_object_or_404(SentInvoice, id=sent_invoice_id)
    if sent_invoice.paid_status != SentInvoice.PaidStatus.NOT_STARTED:
        return redirect(reverse("timary:login"))
    sent_invoice.paid_status = SentInvoice.PaidStatus.PENDING
    sent_invoice.save()

    return render(request, "invoices/success_pay_invoice.html", {})


@require_http_methods(["GET"])
@login_required()
def onboard_success(request):
    if "user_id" not in request.GET:
        return redirect(reverse("timary:register"))
    user = User.objects.filter(id=request.GET.get("user_id")).first()
    if not user:
        return redirect(reverse("timary:register"))

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


def stripe_webhook(request, stripe_secret):
    """
    Test locally => stripe listen --forward-to localhost:8000/stripe-standard-webhook/
    Copy webhook secret into STRIPE_STANDARD_WEBHOOK_SECRET
    """
    payload = request.body
    sig_header = request.META["HTTP_STRIPE_SIGNATURE"]

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, stripe_secret)
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

            msg_body = InvoiceBuilder(sent_invoice.user).send_invoice(
                {
                    "sent_invoice": sent_invoice,
                    "line_items": sent_invoice.get_rendered_line_items(),
                }
            )
            EmailService.send_html(
                f"Unable to process {sent_invoice.invoice.user.first_name}'s invoice. "
                f"An error occurred while trying to "
                f"transfer the funds for this invoice. Please give it another try.",
                msg_body,
                sent_invoice.invoice.client.email,
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
            sent_invoice.date_paid = timezone.now()
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

    elif event["type"] == "invoice.created":
        user_subscription_id = event["data"]["object"]["id"]
        user_found = User.objects.filter(stripe_subscription_id=user_subscription_id)
        if user_found.exists():
            user = user_found.first()
            user.stripe_subscription_status = User.StripeSubscriptionStatus.ACTIVE
            user.save()

            if user.referrer_id:
                referred_user = User.objects.get(referral_id=user.referral_id)
                if referred_user:
                    referred_user.add_referral_discount()

    elif event["type"] in [
        "invoice.finalization_failed",
        "invoice.payment_action_required",
        "invoice.payment_failed",
    ]:
        # Could be any reason, but subscription has failed
        user_subscription_id = event["data"]["object"]["id"]
        user = User.objects.filter(stripe_subscription_id=user_subscription_id)
        if user.exists():
            user = user.first()
            user.stripe_subscription_status = User.StripeSubscriptionStatus.INACTIVE
            user.save()
            EmailService.send_plain(
                "Oops, something went wrong over here at Timary",
                f"""
Hello {user.first_name.capitalize()},

Looks like Stripe had trouble charging your card.

Nothing to worry about, just head to your profile page and update your payment method.

Once that succeeds, then re-activate the subscription and you should be good to go.

If there are any questions, please do not hesitate to reply to this email.

Otherwise, enjoy the rest of your day.
Aristotel F
ari@usetimary.com
                """,
                user.email,
            )
            if not settings.DEBUG:
                print(f"Subscription failed: user_id={user.id}", file=sys.stderr)
    else:
        # ... handle other event types
        print("Unhandled event type {}".format(event["type"]))
    return JsonResponse({"success": True})


@require_http_methods(["POST"])
@csrf_exempt
def stripe_standard_webhook(request):
    return stripe_webhook(request, settings.STRIPE_STANDARD_WEBHOOK_SECRET)


@require_http_methods(["POST"])
@csrf_exempt
def stripe_connect_webhook(request):
    return stripe_webhook(request, settings.STRIPE_CONNECT_WEBHOOK_SECRET)
