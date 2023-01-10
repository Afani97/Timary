import json

import requests
from django.conf import settings
from django.urls import reverse
from requests.auth import HTTPBasicAuth

from timary.custom_errors import AccountingError
from timary.utils import simulate_requests_response


class QuickbooksService:
    @staticmethod
    def get_auth_url():
        redirect_uri = f"{settings.SITE_URL}{reverse('timary:accounting_redirect')}"
        url = (
            f"https://appcenter.intuit.com/connect/oauth2?client_id={settings.QUICKBOOKS_CLIENT_ID}&response_type"
            f"=code&scope=com.intuit.quickbooks.accounting&redirect_uri={redirect_uri}&state=sandbox"
        )
        return url, "quickbooks"

    @staticmethod
    def get_auth_tokens(request):
        redirect_uri = f"{settings.SITE_URL}{reverse('timary:accounting_redirect')}"
        if "code" in request.GET:
            auth_code = request.GET.get("code")
            realm_id = request.GET.get("realmId")
            auth_request = requests.post(
                "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer",
                auth=HTTPBasicAuth(
                    settings.QUICKBOOKS_CLIENT_ID, settings.QUICKBOOKS_SECRET_KEY
                ),
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "grant_type": "authorization_code",
                    "code": auth_code,
                    "redirect_uri": redirect_uri,
                },
            )
            if not auth_request.ok:
                raise AccountingError(
                    user=request.user,
                    requests_response=auth_request,
                )
            response = auth_request.json()

            if "access_token" not in response:
                raise AccountingError(
                    user=request.user,
                    requests_response=auth_request,
                )
            request.user.accounting_refresh_token = response["refresh_token"]
            request.user.accounting_org_id = realm_id
            request.user.save()
            return response["access_token"]
        else:
            failed_response = simulate_requests_response(
                status_code=400,
                error_num=10,
                message="We weren't able to find a valid account. Please re-try adding a Quickbooks account.",
            )
            raise AccountingError(user=request.user, requests_response=failed_response)

    @staticmethod
    def get_refreshed_tokens(user):
        auth_request = requests.post(
            "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer",
            auth=HTTPBasicAuth(
                settings.QUICKBOOKS_CLIENT_ID, settings.QUICKBOOKS_SECRET_KEY
            ),
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "refresh_token",
                "refresh_token": user.accounting_refresh_token,
            },
        )
        if not auth_request.ok:
            raise AccountingError(user=user, requests_response=auth_request)
        response = auth_request.json()
        user.accounting_refresh_token = response["refresh_token"]
        user.save()
        return response["access_token"]

    @staticmethod
    def create_request(auth_token, endpoint, method_type, data=None):
        subdomain = (
            "quickbooks"
            if settings.QUICKBOOKS_ENV == "production"
            else "sandbox-quickbooks"
        )
        base_url = f"https://{subdomain}.api.intuit.com"
        url = f"{base_url}/{endpoint}"
        headers = {
            "Authorization": f"Bearer {auth_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if method_type == "get":
            response = requests.get(url, headers=headers)
            return response.json()
        elif method_type == "post":
            response = requests.post(url, headers=headers, data=json.dumps(data))
            if not response.ok:
                raise AccountingError(requests_response=response)
            return response.json()
        return None

    @staticmethod
    def create_customer(invoice, auth_token=None):
        if auth_token:
            quickbooks_auth_token = auth_token
        else:
            quickbooks_auth_token = QuickbooksService.get_refreshed_tokens(invoice.user)
        endpoint = (
            f"v3/company/{invoice.user.accounting_org_id}/customer?minorversion=63"
        )
        data = {
            "DisplayName": invoice.client_name,
            "FullyQualifiedName": invoice.client_name,
            "PrimaryEmailAddr": {"Address": invoice.client_email},
        }
        try:
            response = QuickbooksService.create_request(
                quickbooks_auth_token, endpoint, "post", data=data
            )
        except AccountingError as ae:
            raise AccountingError(
                user=invoice.user,
                requests_response=ae.requests_response,
            )
        invoice.accounting_customer_id = response["Customer"]["Id"]
        invoice.save()

    @staticmethod
    def create_invoice(sent_invoice, auth_token=None):
        if auth_token:
            quickbooks_auth_token = auth_token
        else:
            quickbooks_auth_token = QuickbooksService.get_refreshed_tokens(
                sent_invoice.user
            )

        # Generate invoice
        endpoint = (
            f"v3/company/{sent_invoice.user.accounting_org_id}/invoice?minorversion=63"
        )
        data = {
            "Line": [
                {
                    "DetailType": "SalesItemLineDetail",
                    "Amount": float(sent_invoice.total_price),
                    "SalesItemLineDetail": {
                        "ItemRef": {"name": "Services", "value": "1"}
                    },
                }
            ],
            "CustomerRef": {"value": sent_invoice.invoice.accounting_customer_id},
        }
        try:
            response = QuickbooksService.create_request(
                quickbooks_auth_token, endpoint, "post", data=data
            )
        except AccountingError as ae:
            raise AccountingError(
                user=sent_invoice.user,
                requests_response=ae.requests_response,
            )
        sent_invoice.accounting_invoice_id = response["Invoice"]["Id"]
        sent_invoice.save()

        # Generate payment for invoice
        endpoint = (
            f"v3/company/{sent_invoice.user.accounting_org_id}/payment?minorversion=63"
        )
        data = {
            "TotalAmt": float(sent_invoice.total_price),
            "CustomerRef": {"value": sent_invoice.invoice.accounting_customer_id},
            "Line": [
                {
                    "Amount": float(sent_invoice.total_price),
                    "LinkedTxn": [
                        {
                            "TxnId": sent_invoice.accounting_invoice_id,
                            "TxnType": "Invoice",
                        }
                    ],
                },
            ],
        }
        try:
            QuickbooksService.create_request(
                quickbooks_auth_token, endpoint, "post", data=data
            )
        except AccountingError as ae:
            raise AccountingError(
                user=sent_invoice.user,
                requests_response=ae.requests_response,
            )

    @staticmethod
    def test_integration(user):
        quickbooks_auth_token = QuickbooksService.get_refreshed_tokens(user)
        endpoint = f"v3/company/{user.accounting_org_id}/customer?minorversion=63"
        data = {
            "DisplayName": "Bob Smith",
            "FullyQualifiedName": "Bob Smith",
            "PrimaryEmailAddr": {"Address": "bob@example.com"},
        }
        try:
            response = QuickbooksService.create_request(
                quickbooks_auth_token, endpoint, "post", data=data
            )
        except AccountingError as ae:
            raise AccountingError(
                user=user,
                requests_response=ae.requests_response,
            )

        customer_id = response["Customer"]["Id"]

        data = {"Active": False, "SyncToken": "0", "Id": customer_id, "sparse": True}
        try:
            QuickbooksService.create_request(
                quickbooks_auth_token, endpoint, "post", data=data
            )
        except AccountingError as ae:
            raise AccountingError(
                user=user,
                requests_response=ae.requests_response,
            )
