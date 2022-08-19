from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from timary.custom_errors import AccountingError
from timary.models import SentInvoice
from timary.services.accounting_service import AccountingService


# Accounting
@login_required
@require_http_methods(["GET"])
def accounting_connect(request):
    accounting_service = request.GET.get("service")
    return redirect(
        AccountingService(
            {"user": request.user, "service": accounting_service}
        ).get_auth_url()
    )


@login_required
@require_http_methods(["GET"])
def accounting_redirect(request):
    user = request.user
    try:
        access_token = AccountingService({"user": user}).get_auth_tokens()
    except AccountingError as ae:
        ae.log(initial_sync=True)
        messages.error(request, f"Unable to connect to {user.accounting_org}.")
        return redirect(reverse("timary:user_profile"))

    if not access_token:
        messages.error(request, "Unable to connect to Sage.")
        return redirect(reverse("timary:user_profile"))

    for invoice in user.get_invoices:
        accounting_service = AccountingService({"user": user, "invoice": invoice})
        if not invoice.accounting_customer_id:
            try:
                accounting_service.create_customer()
            except AccountingError as ae:
                ae.log(initial_sync=True)
                messages.error(
                    request,
                    f"We had trouble syncing your data with {user.accounting_org}.",
                )
                return redirect(reverse("timary:user_profile"))
    for sent_invoice in user.sent_invoices.filter(
        paid_status=SentInvoice.PaidStatus.PAID
    ):
        accounting_service = AccountingService(
            {"user": user, "sent_invoice": sent_invoice}
        )
        if not sent_invoice.accounting_invoice_id:

            try:
                accounting_service.create_invoice()
            except AccountingError as ae:
                ae.log(initial_sync=True)
                messages.error(
                    request,
                    f"We had trouble syncing your data with {user.accounting_org}.",
                )
                return redirect(reverse("timary:user_profile"))

    messages.success(request, "Successfully connected Sage.")
    return redirect(reverse("timary:user_profile"))


@login_required
@require_http_methods(["DELETE"])
def accounting_disconnect(request):
    request.user.account_org = None
    request.user.accounting_org_id = None
    request.user.accounting_refresh_token = None
    request.user.save()
    return render(
        request,
        "partials/settings/_edit_accounting.html",
        {"settings": request.user.settings},
    )
