from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from timary.custom_errors import AccountingError
from timary.models import User
from timary.services.accounting_service import AccountingService


@login_required
@require_http_methods(["GET"])
def accounting_connect(request):
    accounting_service = request.GET.get("service")
    auth_url = AccountingService(
        {"user": request.user, "service": accounting_service}
    ).get_auth_url()
    if not auth_url:
        logout(request)
        return redirect(reverse("timary:register"))
    return redirect(auth_url)


@login_required
@require_http_methods(["GET"])
def accounting_redirect(request):
    user: User = request.user
    try:
        access_token = AccountingService(
            {"user": user, "request": request}
        ).get_auth_tokens()
    except AccountingError as ae:
        error_reason = ae.log(initial_sync=True)
        messages.error(
            request,
            f"We had trouble connecting to {user.accounting_org.title()}.",
            extra_tags="generic-err",
        )
        if error_reason:
            messages.error(request, error_reason, extra_tags="specific-err")
        return redirect(reverse("timary:user_profile"))

    if not access_token:
        messages.error(
            request,
            f"Unable to connect to {user.accounting_org.title()}. Please try again.",
            extra_tags="missing-token-err",
        )
        user.accounting_org = None
        user.save()
        return redirect(reverse("timary:user_profile"))

    messages.success(
        request,
        f"Successfully connected {user.accounting_org.title()}.",
        extra_tags="success-msg",
    )
    return redirect(reverse("timary:user_profile"))


@login_required
@require_http_methods(["DELETE"])
def accounting_disconnect(request):
    user: User = request.user
    user.account_org = None
    user.accounting_org_id = None
    user.accounting_refresh_token = None
    user.get_all_invoices().update(accounting_customer_id=None)
    user.sent_invoices.all().update(accounting_invoice_id=None)
    user.save()
    return render(
        request,
        "partials/settings/account/_edit_accounting.html",
        {"settings": user.settings},
    )


@login_required()
@require_http_methods(["GET"])
def accounting_sync(request):
    accounting_service = AccountingService({"user": request.user})
    # Sync the current invoice customers first
    try:
        accounting_service.sync_customers()
    except AccountingError as ae:
        ae.log()
        messages.error(
            request,
            f"We had trouble syncing your customers with {request.user.accounting_org.title()}.",
        )
        messages.info(
            request,
            "We have noted this error and will reach out to resolve soon.",
        )
        return redirect(reverse("timary:user_profile"))

    # Then sync the current paid sent invoices
    try:
        accounting_service.sync_invoices()
    except AccountingError as ae:
        ae.log()
        messages.error(
            request,
            f"We had trouble syncing your paid invoices with {request.user.accounting_org.title()}.",
        )
        messages.info(
            request,
            "We have noted this error and will reach out to resolve soon.",
        )
        return redirect(reverse("timary:user_profile"))
    messages.success(
        request,
        "success",
        f"Successfully synced all your invoices with {request.user.accounting_org.title()}",
    )
    return redirect(reverse("timary:user_profile"))
