from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from timary.forms import PayInvoiceForm
from timary.models import SentInvoice, User
from timary.services.freshbook_service import FreshbookService
from timary.services.quickbook_service import QuickbookService
from timary.services.sage_service import SageService
from timary.services.stripe_service import StripeService
from timary.services.twilio_service import TwilioClient
from timary.services.xero_service import XeroService
from timary.services.zoho_service import ZohoService


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
            "client_secret": client_secret,
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

    # TODO: Handle confirm errors
    _ = StripeService.confirm_payment(sent_invoice)
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
    if sent_invoice.paid_status == SentInvoice.PaidStatus.PAID:
        return redirect(reverse("timary:login"))
    sent_invoice.paid_status = SentInvoice.PaidStatus.PAID
    sent_invoice.save()

    TwilioClient.sent_payment_success(sent_invoice)

    if sent_invoice.user.quickbooks_realm_id:
        QuickbookService.create_invoice(sent_invoice)

    if sent_invoice.user.freshbooks_account_id:
        FreshbookService.create_invoice(sent_invoice)

    if sent_invoice.user.zoho_organization_id:
        ZohoService.create_invoice(sent_invoice)

    if sent_invoice.user.xero_tenant_id:
        XeroService.create_invoice(sent_invoice)

    if sent_invoice.user.sage_account_id:
        SageService.create_invoice(sent_invoice)

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
