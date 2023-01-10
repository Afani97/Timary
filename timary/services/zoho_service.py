import datetime
import json
import urllib.parse

import requests
from django.conf import settings
from django.urls import reverse

from timary.custom_errors import AccountingError
from timary.models import SentInvoice, SingleInvoice


class ZohoService:
    @staticmethod
    def get_auth_url():
        client_redirect = f"{settings.SITE_URL}{reverse('timary:accounting_redirect')}"
        auth_url = (
            f"https://accounts.zoho.com/oauth/v2/auth?scope=ZohoInvoice.settings.CREATE,ZohoInvoice.settings.READ,"
            f"ZohoInvoice.invoices.CREATE,"
            f"ZohoInvoice.invoices.READ,ZohoInvoice.invoices.UPDATE,ZohoInvoice.contacts.Create,"
            f"ZohoInvoice.contacts.UPDATE,ZohoInvoice.customerpayments.Create,ZohoInvoice.customerpayments.UPDATE"
            f"&client_id={settings.ZOHO_CLIENT_ID}&state=testing&response_type=code&redirect_uri="
            f"{client_redirect}&access_type=offline"
        )
        return auth_url, "zoho"

    @staticmethod
    def get_auth_tokens(request):
        client_redirect = f"{settings.SITE_URL}{reverse('timary:accounting_redirect')}"
        if "code" in request.GET:
            auth_code = request.GET.get("code")

            auth_request = requests.post(
                f"https://accounts.zoho.com/oauth/v2/token?code={auth_code}"
                f"&client_id={settings.ZOHO_CLIENT_ID}&client_secret={settings.ZOHO_SECRET_KEY}"
                f"&redirect_uri={client_redirect}&grant_type=authorization_code"
            )
            if not auth_request.ok:
                raise AccountingError(
                    user=request.user,
                    requests_response=auth_request,
                )

            response = auth_request.json()

            if "access_token" not in response or "refresh_token" not in response:
                raise AccountingError(
                    user=request.user,
                    requests_response=auth_request,
                )

            request.user.accounting_refresh_token = response["refresh_token"]
            try:
                ZohoService.get_organization_id(request.user, response["access_token"])
            except AccountingError as ae:
                raise AccountingError(
                    user=request.user,
                    requests_response=ae.requests_response,
                )
            request.user.save()
            return response["access_token"]
        return None

    @staticmethod
    def get_refreshed_tokens(user):
        client_redirect = f"{settings.SITE_URL}{reverse('timary:accounting_redirect')}"
        refresh_response = requests.post(
            f"https://accounts.zoho.com/oauth/v2/token?refresh_token={user.accounting_refresh_token}"
            f"&client_id={settings.ZOHO_CLIENT_ID}&client_secret={settings.ZOHO_SECRET_KEY}"
            f"&redirect_uri={client_redirect}&grant_type=refresh_token"
        )
        if not refresh_response.ok or "access_token" not in refresh_response.json():
            raise AccountingError(user=user, requests_response=refresh_response)
        response = refresh_response.json()
        return response["access_token"]

    @staticmethod
    def create_request(auth_token, org_id, endpoint, method_type, data=None):
        base_url = "https://invoice.zoho.com/api/v3"
        url = f"{base_url}/{endpoint}?organization_id={org_id}"
        headers = {
            "Authorization": f"Zoho-oauthtoken {auth_token}",
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        }
        if method_type == "get":
            response = requests.get(url, headers=headers)
            return response.json()
        elif method_type == "post":
            response = requests.post(
                url,
                headers=headers,
                data=urllib.parse.urlencode({"JSONString": json.dumps(data)}),
            )
            if not response.ok:
                raise AccountingError(requests_response=response)
            return response.json()
        if method_type == "delete":
            response = requests.delete(url, headers=headers)
            return response.json()
        return None

    @staticmethod
    def get_organization_id(user, access_token):
        zoho_org_request = requests.get(
            "https://invoice.zoho.com/api/v3/organizations",
            headers={"Authorization": f"Zoho-oauthtoken {access_token}"},
        )
        if not zoho_org_request.ok:
            raise AccountingError(requests_response=zoho_org_request)
        zoho_org_response = zoho_org_request.json()
        if zoho_org_response["message"] == "success":
            user.accounting_org_id = zoho_org_response["organizations"][0][
                "organization_id"
            ]
            user.save()

    @staticmethod
    def create_customer(invoice, auth_token=None):
        if auth_token:
            zoho_auth_token = auth_token
        else:
            zoho_auth_token = ZohoService.get_refreshed_tokens(invoice.user)

        recipient_name = invoice.client_name.split(" ")
        data = {
            "contact_name": invoice.client_name,
            "email": invoice.client_email,
            "contact_persons": [
                {
                    "first_name": recipient_name[0],
                    "last_name": recipient_name[1],
                    "email": invoice.client_email,
                    "is_primary_contact": True,
                }
            ],
        }
        try:
            response = ZohoService.create_request(
                zoho_auth_token,
                invoice.user.accounting_org_id,
                "contacts",
                "post",
                data=data,
            )
        except AccountingError as ae:
            raise AccountingError(
                user=invoice.user,
                requests_response=ae.requests_response,
            )
        if "contact" not in response or "contact_id" not in response["contact"]:
            raise AccountingError(
                user=invoice.user,
                requests_response=response,
            )
        invoice.accounting_customer_id = response["contact"]["contact_id"]
        invoice.save()

    @staticmethod
    def create_invoice(sent_invoice, auth_token=False):
        if auth_token:
            zoho_auth_token = auth_token
        else:
            zoho_auth_token = ZohoService.get_refreshed_tokens(sent_invoice.user)

        today = datetime.date.today() + datetime.timedelta(days=1)
        today_formatted = today.strftime("%Y-%m-%d")

        # Generate item
        data = {
            "rate": float(sent_invoice.total_price),
        }
        if isinstance(sent_invoice, SentInvoice):
            data.update(
                {
                    "name": f"{sent_invoice.user.first_name} services on {today_formatted} for {sent_invoice.invoice.title}",
                }
            )
        elif isinstance(sent_invoice, SingleInvoice):
            data.update(
                {
                    "name": f"{sent_invoice.user.first_name} services on {today_formatted} for {sent_invoice.title}"
                }
            )
        try:
            item_request = ZohoService.create_request(
                zoho_auth_token,
                sent_invoice.user.accounting_org_id,
                "items",
                "post",
                data=data,
            )
        except AccountingError as ae:
            raise AccountingError(
                user=sent_invoice.user,
                requests_response=ae.requests_response,
            )

        item_id = item_request["item"]["item_id"]

        # Mark line item as active
        try:
            ZohoService.create_request(
                zoho_auth_token,
                sent_invoice.user.accounting_org_id,
                f"items/{item_id}/active",
                "post",
            )
        except AccountingError as ae:
            raise AccountingError(
                user=sent_invoice.user,
                requests_response=ae.requests_response,
            )

        # Generate invoice
        data = {
            "date": today_formatted,
            "line_items": [
                {
                    "item_id": item_id,
                    "rate": int(float(sent_invoice.total_price)),
                    "quantity": 1,
                    "item_total": int(float(sent_invoice.total_price)),
                }
            ],
        }
        if isinstance(sent_invoice, SentInvoice):
            data.update(
                {
                    "customer_id": sent_invoice.invoice.accounting_customer_id,
                }
            )
        elif isinstance(sent_invoice, SingleInvoice):
            data.update(
                {
                    "customer_id": sent_invoice.accounting_customer_id,
                }
            )
        try:
            response = ZohoService.create_request(
                zoho_auth_token,
                sent_invoice.user.accounting_org_id,
                "invoices",
                "post",
                data=data,
            )
        except AccountingError as ae:
            raise AccountingError(
                user=sent_invoice.user,
                requests_response=ae.requests_response,
            )
        if "invoice" not in response or "invoice_id" not in response["invoice"]:
            raise AccountingError(
                user=sent_invoice.user,
                requests_response=response,
            )
        sent_invoice.accounting_invoice_id = response["invoice"]["invoice_id"]
        sent_invoice.save()

        # Generate payment for invoice
        data = {
            "payment_mode": "creditcard",
            "amount": int(float(sent_invoice.total_price)),
            "date": today_formatted,
            "invoices": [
                {
                    "invoice_id": sent_invoice.accounting_invoice_id,
                    "amount_applied": int(float(sent_invoice.total_price)),
                }
            ],
        }
        if isinstance(sent_invoice, SentInvoice):
            data.update(
                {
                    "customer_id": sent_invoice.invoice.accounting_customer_id,
                }
            )
        elif isinstance(sent_invoice, SingleInvoice):
            data.update(
                {
                    "customer_id": sent_invoice.accounting_customer_id,
                }
            )
        try:
            ZohoService.create_request(
                zoho_auth_token,
                sent_invoice.user.accounting_org_id,
                "customerpayments",
                "post",
                data=data,
            )
        except AccountingError as ae:
            raise AccountingError(
                user=sent_invoice.user,
                requests_response=ae.requests_response,
            )

    @staticmethod
    def test_integration(user):
        zoho_auth_token = ZohoService.get_refreshed_tokens(user)

        data = {
            "contact_name": "Bob Smith",
            "email": "bob@example.com",
            "contact_persons": [
                {
                    "first_name": "Bob",
                    "last_name": "Smith",
                    "email": "bob@example.com",
                    "is_primary_contact": True,
                }
            ],
        }
        try:
            response = ZohoService.create_request(
                zoho_auth_token,
                user.accounting_org_id,
                "contacts",
                "post",
                data=data,
            )
        except AccountingError as ae:
            raise AccountingError(
                user=user,
                requests_response=ae.requests_response,
            )
        if "contact" not in response or "contact_id" not in response["contact"]:
            raise AccountingError(
                user=user,
                requests_response=response,
            )
        customer_id = response["contact"]["contact_id"]

        try:
            ZohoService.create_request(
                zoho_auth_token,
                user.accounting_org_id,
                f"contacts/{customer_id}",
                "delete",
            )
        except AccountingError as ae:
            raise AccountingError(
                user=user,
                requests_response=ae.requests_response,
            )
