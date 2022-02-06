from django.shortcuts import redirect
from django.urls import reverse

from timary.services.quickbook_service import QuickbooksClient


def quickbooks_connect(request):
    return redirect(QuickbooksClient.get_auth_url())


def quickbooks_redirect(request):
    _ = QuickbooksClient.get_auth_tokens(request)

    return redirect(reverse("timary:user_profile"))
