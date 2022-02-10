from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from timary.services.quickbook_service import QuickbooksClient


@login_required
@require_http_methods(["GET"])
def quickbooks_connect(request):
    return redirect(QuickbooksClient.get_auth_url())


@login_required
@require_http_methods(["GET"])
def quickbooks_redirect(request):
    _ = QuickbooksClient.get_auth_tokens(request)

    return redirect(reverse("timary:user_profile"))


@login_required
@require_http_methods(["DELETE"])
def quickbooks_disconnect(request):
    request.user.quickbooks_realm_id = None
    request.user.save()
    return render(
        request, "partials/_integrations.html", {"settings": request.user.settings}
    )
