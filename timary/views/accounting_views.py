from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from timary.custom_errors import AccountingError
from timary.models import Client, SentInvoice, User
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
    accounting_service = AccountingService({"user": user, "request": request})
    try:
        access_token = accounting_service.get_auth_tokens()
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

    try:
        accounting_service.test_integration()
    except AccountingError as ae:
        error_reason = ae.log(initial_sync=True)
        messages.error(
            request,
            f"We had trouble integrating with {user.accounting_org.title()}.",
            extra_tags="integration-err",
        )
        if error_reason:
            messages.error(request, error_reason, extra_tags="specific-err")
        return redirect(reverse("timary:user_profile"))

    messages.success(
        request,
        f"Successfully connected {user.accounting_org.title()}.",
        extra_tags="success-msg",
    )
    if not user.onboarding_tasks["accounting_service_connected"]:
        user.onboarding_tasks["accounting_service_connected"] = True
        user.save()
    return redirect(reverse("timary:user_profile"))


@login_required
@require_http_methods(["DELETE"])
def accounting_disconnect(request):
    user: User = request.user
    user.accounting_org = None
    user.accounting_org_id = None
    user.accounting_refresh_token = None
    user.my_clients.all().update(accounting_customer_id=None)
    user.sent_invoices.all().update(accounting_invoice_id=None)
    user.save()
    return render(
        request,
        "partials/settings/bookkeeping/_edit_accounting.html",
        {"settings": user.settings},
    )


@login_required()
@require_http_methods(["GET"])
def accounting_sync(request):
    if not request.user.settings["subscription_active"]:
        return HttpResponse(
            "Your account is in-active. Please re-activate to sync your invoices."
        )
    accounting_service = AccountingService({"user": request.user})
    # Sync the current invoice customers first
    clients = []
    auth_token = accounting_service.get_request_auth_token()
    for client in request.user.my_clients.all():
        synced_client = {
            "client_email": client.email,
            "client_name": client.name,
            "customer_synced": True,
            "customer_synced_error": None,
        }
        if not client.accounting_customer_id:
            try:
                accounting_service.service_klass().create_customer(client, auth_token)
            except AccountingError as ae:
                synced_client["customer_synced_error"] = ae.log()
                synced_client["customer_synced"] = False
        clients.append(synced_client)

    sent_invoices = []
    for invoice in request.user.get_all_invoices():
        # Sync your sent invoices if not already
        synced_sent_invoices = []
        for sent_invoice in invoice.invoice_snapshots.exclude(
            paid_status=SentInvoice.PaidStatus.CANCELLED
        ):
            sent_invoice_synced = True
            sent_invoice_synced_error = None

            if sent_invoice.is_synced:
                synced_sent_invoices.append(
                    (sent_invoice, sent_invoice_synced, sent_invoice_synced_error)
                )
                continue
            elif (
                sent_invoice.paid_status != SentInvoice.PaidStatus.PAID
                and sent_invoice.accounting_invoice_id is None
            ):
                sent_invoice_synced = False
                sent_invoice_synced_error = "Cannot sync because invoice isn't paid yet"
            else:
                # Only sync if invoice isn't synced and paid already
                try:
                    accounting_service.service_klass().create_invoice(
                        sent_invoice, auth_token
                    )
                except AccountingError as ae:
                    sent_invoice_synced_error = ae.log()
                    sent_invoice_synced = False
            synced_sent_invoices.append(
                (sent_invoice, sent_invoice_synced, sent_invoice_synced_error)
            )
        sent_invoices.append({"synced_sent_invoices": synced_sent_invoices})

    total_clients = Client.objects.filter(user=request.user).count()
    total_clients_synced = Client.objects.filter(
        user=request.user, accounting_customer_id__isnull=False
    ).count()
    total_sent_invoices = (
        SentInvoice.objects.filter(user=request.user)
        .exclude(paid_status=SentInvoice.PaidStatus.CANCELLED)
        .count()
    )
    total_sent_invoices_synced = (
        SentInvoice.objects.filter(
            Q(user=request.user) & Q(accounting_invoice_id__isnull=False)
        )
        .exclude(paid_status=SentInvoice.PaidStatus.CANCELLED)
        .count()
    )

    return render(
        request,
        "invoices/_synced_results.html",
        {
            "clients": clients,
            "synced_sent_invoices": sent_invoices,
            "total_sent_invoices": total_sent_invoices,
            "total_sent_invoices_synced": total_sent_invoices_synced,
            "total_clients_synced": total_clients_synced,
            "total_clients": total_clients,
        },
    )
