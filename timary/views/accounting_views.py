import requests
from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse
from intuitlib.client import AuthClient
from intuitlib.enums import Scopes


def quickbooks_connect(request):
    redirect_uri = request.build_absolute_uri(reverse("timary:quickbooks_redirect"))
    auth_client = AuthClient(
        settings.QUICKBOOKS_CLIENT_ID,
        settings.QUICKBOOKS_SECRET_KEY,
        redirect_uri,
        "sandbox",
    )
    url = auth_client.get_authorization_url([Scopes.ACCOUNTING])
    return redirect(url)


def quickbooks_redirect(request):
    auth_code = request.GET.get("code")
    realm_id = request.GET.get("realmId")
    redirect_uri = request.build_absolute_uri(reverse("timary:quickbooks_redirect"))
    auth_client = AuthClient(
        settings.QUICKBOOKS_CLIENT_ID,
        settings.QUICKBOOKS_SECRET_KEY,
        redirect_uri,
        "sandbox",
    )
    auth_client.get_bearer_token(auth_code, realm_id=realm_id)

    request.user.quickbooks_realm_id = realm_id
    request.user.save()

    base_url = "https://sandbox-quickbooks.api.intuit.com"
    url = f"{base_url}/v3/company/{auth_client.realm_id}/companyinfo/{auth_client.realm_id}"
    auth_header = "Bearer {0}".format(auth_client.access_token)
    headers = {"Authorization": auth_header, "Accept": "application/json"}
    response = requests.get(url, headers=headers)
    print(vars(response))

    return redirect(reverse("timary:user_profile"))
