import sys

import stripe
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from timary.custom_errors import AccountingError
from timary.forms import ClientForm
from timary.models import Client
from timary.services.accounting_service import AccountingService
from timary.services.stripe_service import StripeService
from timary.utils import show_alert_message


@login_required()
@require_http_methods(["GET"])
def get_clients(request):
    clients = request.user.my_clients.order_by("name")
    context = {
        "clients": clients,
    }
    return render(
        request,
        "clients/list.html",
        context,
    )


@login_required()
@require_http_methods(["GET"])
def get_client(request, client_id):
    client = Client.objects.get(id=client_id)
    if request.user != client.user:
        raise Http404
    return render(request, "clients/_client.html", {"client": client})


@login_required()
@require_http_methods(["GET"])
def get_accounting_clients(request):
    if request.user.accounting_org is None:
        response = get_clients(request)
        show_alert_message(
            response,
            "error",
            f"Unable to sync clients from {request.user.accounting_org.title()}",
            persist=True,
        )
        return response
    accounting_service = AccountingService({"user": request.user})
    try:
        customers = accounting_service.get_customers()
    except AccountingError as ae:
        ae.log()
        response = get_clients(request)
        show_alert_message(
            response,
            "error",
            f"Unable to sync clients from {request.user.accounting_org.title()}",
            persist=True,
        )
        return response
    for customer in customers:
        if not Client.objects.filter(
            user=request.user, accounting_customer_id=customer["accounting_customer_id"]
        ).exists():
            customer_form = ClientForm(customer)
            if customer_form.is_valid():
                new_client = customer_form.save(commit=False)
                new_client.user = request.user
                new_client.save()
    if len(customers) > 0:
        if not request.user.onboarding_tasks["first_client"]:
            request.user.onboarding_tasks["first_client"] = True
            request.user.save()
    response = get_clients(request)
    show_alert_message(
        response,
        "success",
        f"Clients synced from {request.user.accounting_org.title()}",
    )
    return response


@login_required()
@require_http_methods(["GET", "POST"])
def create_client(request):
    client_form = ClientForm(request.POST or None)
    if client_form.is_valid():
        client_saved = client_form.save(commit=False)
        client_saved.user = request.user
        client_saved.save()
        client_saved.sync_customer()
        user = request.user
        if not user.onboarding_tasks["first_client"]:
            user.onboarding_tasks["first_client"] = True
            user.save()
        response = render(request, "clients/_client.html", {"client": client_saved})
        response[
            "HX-Trigger-After-Swap"
        ] = "clearClientModal"  # To trigger modal closing
        return response
    else:
        return render(request, "clients/_form.html", {"form": client_form})


@login_required()
@require_http_methods(["GET", "POST"])
def update_client(request, client_id):
    client = Client.objects.get(id=client_id)
    if request.user != client.user:
        raise Http404
    client_form = ClientForm(request.POST or None, instance=client)
    if client_form.is_valid():
        client_saved = client_form.save()
        if client_saved.stripe_customer_id:
            try:
                StripeService.update_customer(client_saved)
            except stripe.error.InvalidRequestError as e:
                print(str(e), file=sys.stderr)

        if client_saved.accounting_customer_id:
            accounting_service = AccountingService(
                {"user": request.user, "client": client_saved}
            )
            try:
                accounting_service.update_customer()
            except AccountingError as ae:
                ae.log()
        client_saved.refresh_from_db()
        return render(request, "clients/_client.html", {"client": client_saved})
    else:
        return render(request, "clients/_form.html", {"form": client_form})


@login_required()
@require_http_methods(["GET"])
def sync_client(request, client_id):
    client = Client.objects.get(id=client_id)
    if request.user != client.user:
        raise Http404

    response = render(request, "clients/_client.html", {"client": client})

    if not client.user.settings["subscription_active"]:
        show_alert_message(
            response,
            "warning",
            "Unable to sync invoice, your subscription is inactive.",
        )
        return response

    customer_synced, error_raised = client.sync_customer()

    if customer_synced:
        show_alert_message(
            response,
            "success",
            f"{client.name.title()} is now synced with {client.user.accounting_org}",
        )
    else:
        show_alert_message(
            response,
            "error",
            f"We had trouble syncing {client.name.title()}. {error_raised}",
            persist=True,
        )
    return response
