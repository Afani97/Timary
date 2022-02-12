from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from timary.services.freshbook_service import FreshbookService
from timary.services.quickbook_service import QuickbookService


# QUICKBOOKS
@login_required
@require_http_methods(["GET"])
def quickbooks_connect(request):
    return redirect(QuickbookService.get_auth_url())


@login_required
@require_http_methods(["GET"])
def quickbooks_redirect(request):
    _ = QuickbookService.get_auth_tokens(request)

    return redirect(reverse("timary:user_profile"))


@login_required
@require_http_methods(["DELETE"])
def quickbooks_disconnect(request):
    request.user.quickbooks_realm_id = None
    request.user.save()
    return render(
        request, "partials/_integrations.html", {"settings": request.user.settings}
    )


# FRESHBOOKS
@login_required
@require_http_methods(["GET"])
def freshbooks_connect(request):
    return redirect(FreshbookService.get_auth_url())


@login_required
@require_http_methods(["GET"])
def freshbooks_redirect(request):
    _ = FreshbookService.get_auth_tokens(request)
    return redirect(reverse("timary:user_profile"))


@login_required
@require_http_methods(["DELETE"])
def freshbooks_disconnect(request):
    request.user.freshbooks_account_id = None
    request.user.save()
    return render(
        request, "partials/_integrations.html", {"settings": request.user.settings}
    )
