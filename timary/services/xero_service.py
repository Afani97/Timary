import datetime
import json

import requests
from django.conf import settings
from django.urls import reverse
from requests.auth import HTTPBasicAuth

from timary.custom_errors import AccountingError


class XeroService:
    @staticmethod
    def get_auth_url():
        redirect_uri = f"{settings.SITE_URL}{reverse('timary:xero_redirect')}"
        url = (
            f"https://login.xero.com/identity/connect/authorize?response_type=code"
            f"&client_id={settings.XERO_CLIENT_ID}&redirect_uri={redirect_uri}"
            f"&scope=offline_access openid profile email accounting.contacts accounting.transactions&state=123"
        )
        return url

    @staticmethod
    def get_auth_tokens(request):
        redirect_uri = f"{settings.SITE_URL}{reverse('timary:xero_redirect')}"
        if "code" in request.GET:
            auth_code = request.GET.get("code")

            auth_request = requests.post(
                "https://identity.xero.com/connect/token",
                auth=HTTPBasicAuth(settings.XERO_CLIENT_ID, settings.XERO_SECRET_KEY),
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "grant_type": "authorization_code",
                    "code": auth_code,
                    "redirect_uri": redirect_uri,
                },
            )
            if auth_request.status_code != requests.codes.ok:
                raise AccountingError(
                    user_id=request.user.id, requests_response=auth_request
                )
            response = auth_request.json()

            request.user.xero_refresh_token = response["refresh_token"]
            request.user.save()

            url = "https://api.xero.com/connections"
            tenant_request = requests.get(
                url,
                headers={
                    "Authorization": "Bearer " + response["access_token"],
                    "Content-Type": "application/json",
                },
            )
            if tenant_request.status_code != requests.codes.ok:
                raise AccountingError(
                    user_id=request.user.id, requests_response=tenant_request
                )
            tenant_response = tenant_request.json()
            request.user.xero_tenant_id = tenant_response[0]["tenantId"]
            request.user.save()

    @staticmethod
    def get_refreshed_tokens(user):
        refresh_request = requests.post(
            "https://identity.xero.com/connect/token",
            auth=HTTPBasicAuth(settings.XERO_CLIENT_ID, settings.XERO_SECRET_KEY),
            data={
                "grant_type": "refresh_token",
                "refresh_token": user.xero_refresh_token,
            },
        )
        if refresh_request.status_code != requests.codes.ok:
            raise AccountingError(user_id=user.id, requests_response=refresh_request)
        response = refresh_request.json()
        user.xero_refresh_token = response["refresh_token"]
        user.save()
        return response["access_token"]

    @staticmethod
    def create_request(auth_token, tenant_id, endpoint, method_type, data=None):
        base_url = "https://api.xero.com/api.xro/2.0"
        url = f"{base_url}/{endpoint}"
        headers = {
            "Authorization": f"Bearer {auth_token}",
            "Accept": "application/json",
            "Xero-tenant-id": tenant_id,
        }
        if method_type == "get":
            response = requests.get(url, headers=headers)
            return response.json()
        elif method_type == "post":
            response = requests.post(url, headers=headers, data=json.dumps(data))
            return response.json()
        elif method_type == "put":
            response = requests.put(url, headers=headers, data=json.dumps(data))
            return response.json()
        else:
            return None

    @staticmethod
    def create_customer(invoice):
        try:
            xero_auth_token = XeroService.get_refreshed_tokens(invoice.user)
        except AccountingError as ae:
            accounting_error = AccountingError(
                user_id=invoice.user.id, requests_response=ae.requests_response
            )
            accounting_error.log()
            return
        data = {
            "Name": invoice.email_recipient_name,
            "EmailAddress": invoice.email_recipient,
        }

        try:
            response = XeroService.create_request(
                xero_auth_token,
                invoice.user.xero_tenant_id,
                "Contacts",
                "post",
                data=data,
            )
        except AccountingError as ae:
            accounting_error = AccountingError(
                user_id=invoice.user.id, requests_response=ae.requests_response
            )
            accounting_error.log()
            return
        invoice.xero_contact_id = response["Contacts"][0]["ContactID"]
        invoice.save()

    @staticmethod
    def create_invoice(sent_invoice):
        try:
            xero_auth_token = XeroService.get_refreshed_tokens(sent_invoice.user)
        except AccountingError as ae:
            ae.log()
            return

        # Generate invoice
        today = datetime.date.today() + datetime.timedelta(days=1)
        today_formatted = today.strftime("%Y-%m-%d")
        data = {
            "Type": "ACCREC",
            "Contact": {"ContactID": sent_invoice.invoice.xero_contact_id},
            "DueDate": today_formatted,
            "LineAmountTypes": "Exclusive",
            "Status": "AUTHORISED",
            "LineItems": [
                {
                    "Description": f"{sent_invoice.user.first_name} services",
                    "Quantity": "1",
                    "UnitAmount": sent_invoice.total_price,
                    "AccountCode": "400",
                    "TaxType": "NONE",
                }
            ],
        }
        try:
            response = XeroService.create_request(
                xero_auth_token,
                sent_invoice.user.xero_tenant_id,
                "Invoices",
                "post",
                data=data,
            )
        except AccountingError as ae:
            accounting_error = AccountingError(
                user_id=sent_invoice.user.id, requests_response=ae.requests_response
            )
            accounting_error.log()
            return

        sent_invoice.xero_invoice_id = response["Invoices"][0]["InvoiceID"]
        sent_invoice.save()

        # Generate payment for invoice
        data = {
            "Invoice": {"InvoiceID": sent_invoice.xero_invoice_id},
            "Account": {"Code": "400"},
            "Date": today_formatted,
            "Amount": sent_invoice.total_price,
            "Status": "AUTHORISED",
        }
        try:
            XeroService.create_request(
                xero_auth_token,
                sent_invoice.user.xero_tenant_id,
                "Payments",
                "put",
                data=data,
            )
        except AccountingError as ae:
            accounting_error = AccountingError(
                user_id=sent_invoice.user.id, requests_response=ae.requests_response
            )
            accounting_error.log()
            return
