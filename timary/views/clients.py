from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from timary.forms import ClientForm


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
@require_http_methods(["GET", "POST"])
def create_client(request):
    client_form = ClientForm(request.POST or None)
    if client_form.is_valid():
        client_saved = client_form.save(commit=False)
        client_saved.user = request.user
        client_saved.save()
        client_saved.sync_customer()
        return render(request, "clients/_client.html", {"client": client_saved})
    else:
        return render(request, "clients/_form.html", {"form": client_form})
