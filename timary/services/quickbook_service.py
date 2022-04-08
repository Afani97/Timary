import json

import requests
from django.conf import settings
from django.urls import reverse
from requests.auth import HTTPBasicAuth

from timary.custom_errors import AccountingError


class QuickbookService:
    @staticmethod
    def get_auth_url():
        redirect_uri = f"{settings.SITE_URL}{reverse('timary:quickbooks_redirect')}"
        return (
            f"https://appcenter.intuit.com/connect/oauth2?client_id={settings.QUICKBOOKS_CLIENT_ID}&response_type"
            f"=code&scope=com.intuit.quickbooks.accounting&redirect_uri={redirect_uri}&state=sandbox"
        )

    @staticmethod
    def get_auth_tokens(request):
        redirect_uri = f"{settings.SITE_URL}{reverse('timary:quickbooks_redirect')}"
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
                    service="Quickbooks",
                    user_id=request.user.id,
                    requests_response=auth_request,
                )
            response = auth_request.json()

            request.user.quickbooks_refresh_token = response["refresh_token"]
            request.user.quickbooks_realm_id = realm_id
            request.user.save()
            return response["access_token"]

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
                "refresh_token": user.quickbooks_refresh_token,
            },
        )
        if not auth_request.ok:
            raise AccountingError(
                service="Quickbooks", user_id=user.id, requests_response=auth_request
            )
        response = auth_request.json()
        user.quickbooks_refresh_token = response["refresh_token"]
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
    def create_customer(invoice):
        try:
            quickbooks_auth_token = QuickbookService.get_refreshed_tokens(invoice.user)
        except AccountingError as ae:
            ae.log()
            return
        endpoint = (
            f"v3/company/{invoice.user.quickbooks_realm_id}/customer?minorversion=63"
        )
        data = {
            "DisplayName": invoice.email_recipient_name,
            "FullyQualifiedName": invoice.email_recipient_name,
            "PrimaryEmailAddr": {"Address": invoice.email_recipient},
        }
        try:
            response = QuickbookService.create_request(
                quickbooks_auth_token, endpoint, "post", data=data
            )
        except AccountingError as ae:
            accounting_error = AccountingError(
                service="Quickbooks",
                user_id=invoice.user.id,
                requests_response=ae.requests_response,
            )
            accounting_error.log()
            return
        invoice.quickbooks_customer_ref_id = response["Customer"]["Id"]
        invoice.save()

    @staticmethod
    def create_invoice(sent_invoice):
        try:
            quickbooks_auth_token = QuickbookService.get_refreshed_tokens(
                sent_invoice.user
            )
        except AccountingError as ae:
            ae.log()
            return

        # Generate invoice
        endpoint = f"v3/company/{sent_invoice.user.quickbooks_realm_id}/invoice?minorversion=63"
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
            "CustomerRef": {"value": sent_invoice.invoice.quickbooks_customer_ref_id},
        }
        try:
            response = QuickbookService.create_request(
                quickbooks_auth_token, endpoint, "post", data=data
            )
        except AccountingError as ae:
            accounting_error = AccountingError(
                service="Quickbooks",
                user_id=sent_invoice.user.id,
                requests_response=ae.requests_response,
            )
            accounting_error.log()
            return
        sent_invoice.quickbooks_invoice_id = response["Invoice"]["Id"]
        sent_invoice.save()

        # Generate payment for invoice
        endpoint = f"v3/company/{sent_invoice.user.quickbooks_realm_id}/payment?minorversion=63"
        data = {
            "TotalAmt": float(sent_invoice.total_price),
            "CustomerRef": {"value": sent_invoice.invoice.quickbooks_customer_ref_id},
            "Line": [
                {
                    "Amount": float(sent_invoice.total_price),
                    "LinkedTxn": [
                        {
                            "TxnId": sent_invoice.quickbooks_invoice_id,
                            "TxnType": "Invoice",
                        }
                    ],
                },
            ],
        }
        try:
            QuickbookService.create_request(
                quickbooks_auth_token, endpoint, "post", data=data
            )
        except AccountingError as ae:
            accounting_error = AccountingError(
                service="Quickbooks",
                user_id=sent_invoice.user.id,
                requests_response=ae.requests_response,
            )
            accounting_error.log()
            return
