from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from timary.services.freshbook_service import FreshbookService
from timary.services.quickbook_service import QuickbookService
from timary.services.sage_service import SageService
from timary.services.xero_service import XeroService

# QUICKBOOKS
from timary.services.zoho_service import ZohoService


@login_required
@require_http_methods(["GET"])
def quickbooks_connect(request):
    return redirect(QuickbookService.get_auth_url())


@login_required
@require_http_methods(["GET"])
def quickbooks_redirect(request):
    _ = QuickbookService.get_auth_tokens(request)
    messages.info(request, "Successfully connected Quickbooks.")
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
    auth_token = FreshbookService.get_auth_tokens(request)
    if auth_token:
        FreshbookService.get_current_user(request.user, auth_token)
        messages.info(request, "Successfully connected Freshbooks.")
    return redirect(reverse("timary:user_profile"))


@login_required
@require_http_methods(["DELETE"])
def freshbooks_disconnect(request):
    request.user.freshbooks_account_id = None
    request.user.save()
    return render(
        request, "partials/_integrations.html", {"settings": request.user.settings}
    )


# ZOHO
@login_required
@require_http_methods(["GET"])
def zoho_connect(request):
    return redirect(ZohoService.get_auth_url())


@login_required
@require_http_methods(["GET"])
def zoho_redirect(request):
    access_token = ZohoService.get_auth_tokens(request)
    if access_token:
        ZohoService.get_organization_id(request.user, access_token)
        messages.info(request, "Successfully connected Zoho.")
    else:
        messages.info(request, "Unable to connect to Zoho")
    return redirect(reverse("timary:user_profile"))


@login_required
@require_http_methods(["DELETE"])
def zoho_disconnect(request):
    request.user.zoho_organization_id = None
    request.user.save()
    return render(
        request, "partials/_integrations.html", {"settings": request.user.settings}
    )


# XERO
@login_required
@require_http_methods(["GET"])
def xero_connect(request):
    return redirect(XeroService.get_auth_url())


@login_required
@require_http_methods(["GET"])
def xero_redirect(request):
    _ = XeroService.get_auth_tokens(request)
    messages.info(request, "Successfully connected Xero.")
    return redirect(reverse("timary:user_profile"))


@login_required
@require_http_methods(["DELETE"])
def xero_disconnect(request):
    request.user.xero_tenant_id = None
    request.user.save()
    return render(
        request, "partials/_integrations.html", {"settings": request.user.settings}
    )


# SAGE
@login_required
@require_http_methods(["GET"])
def sage_connect(request):
    return redirect(SageService.get_auth_url())


@login_required
@require_http_methods(["GET"])
def sage_redirect(request):
    _ = SageService.get_auth_tokens(request)
    messages.info(request, "Successfully connected Sage.")
    return redirect(reverse("timary:user_profile"))


@login_required
@require_http_methods(["DELETE"])
def sage_disconnect(request):
    request.user.sage_account_id = None
    request.user.save()
    return render(
        request, "partials/_integrations.html", {"settings": request.user.settings}
    )
