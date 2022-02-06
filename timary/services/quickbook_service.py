import json

import requests
from django.conf import settings
from django.urls import reverse
from intuitlib.client import AuthClient
from intuitlib.enums import Scopes


class QuickbooksClient:
    base_url = "https://sandbox-quickbooks.api.intuit.com"
    access_token = None
    refresh_token = None

    @staticmethod
    def get_auth_client():
        auth_client = AuthClient(
            settings.QUICKBOOKS_CLIENT_ID,
            settings.QUICKBOOKS_SECRET_KEY,
            f"{settings.SITE_URL}{reverse('timary:quickbooks_redirect')}",
            settings.QUICKBOOKS_ENV,
        )
        return auth_client

    @staticmethod
    def get_auth_url():
        auth_client = QuickbooksClient.get_auth_client()
        return auth_client.get_authorization_url([Scopes.ACCOUNTING])

    @staticmethod
    def get_auth_tokens(request):
        auth_code = request.GET.get("code")
        realm_id = request.GET.get("realmId")
        auth_client = QuickbooksClient.get_auth_client()
        auth_client.get_bearer_token(auth_code, realm_id=realm_id)

        request.user.quickbooks_realm_id = realm_id
        request.user.save()

        QuickbooksClient.access_token = auth_client.access_token
        QuickbooksClient.refresh_token = auth_client.refresh_token

        return auth_client.access_token

    @staticmethod
    def get_refreshed_tokens():
        auth_client = QuickbooksClient.get_auth_client()
        auth_client.refresh(QuickbooksClient.refresh_token)
        QuickbooksClient.access_token = auth_client.access_token
        QuickbooksClient.refresh_token = auth_client.refresh_token
        return auth_client.access_token

    @staticmethod
    def create_request(endpoint, method_type, data=None):
        base_url = "https://sandbox-quickbooks.api.intuit.com"
        url = f"{base_url}/{endpoint}"
        headers = {
            "Authorization": f"Bearer {QuickbooksClient.get_refreshed_tokens()}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if method_type == "get":
            response = requests.get(url, headers=headers)
            return response.json()
        elif method_type == "post":
            response = requests.post(url, headers=headers, data=json.dumps(data))
            return response.json()
        else:
            return None

    @staticmethod
    def create_customer(invoice):
        endpoint = f"v3/company/{invoice.user.realm_id}/customer?minorversion=63"
        data = {
            "DisplayName": invoice.email_recipient_name,
            "FullyQualifiedName": invoice.email_recipient_name,
            "PrimaryEmailAddr": {"Address": invoice.email_recipient},
        }
        response = QuickbooksClient.create_request(endpoint, "post", data=data)
        invoice.quickbooks_customer_ref_id = response["Customer"]["Id"]
        invoice.save()

    @staticmethod
    def create_invoice(sent_invoice):
        endpoint = f"v3/company/{sent_invoice.user.quickbooks_realm_id}/invoice?minorversion=63"
        data = {
            "Line": [
                {
                    "DetailType": "SalesItemLineDetail",
                    "Amount": sent_invoice.total_price,
                    "SalesItemLineDetail": {
                        "ItemRef": {"name": "Services", "value": "1"}
                    },
                }
            ],
            "CustomerRef": {"value": sent_invoice.invoice.quickbooks_customer_ref_id},
        }
        response = QuickbooksClient.create_request(endpoint, "post", data=data)
        sent_invoice.quickbooks_invoice_id = response["Invoice"]["Id"]
        sent_invoice.save()
