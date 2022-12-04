import datetime
import json

import requests
from django.conf import settings
from django.urls import reverse

from timary.custom_errors import AccountingError


class FreshbooksService:
    @staticmethod
    def get_domain():
        ngrok_local_url = "https://626e-71-87-212-255.ngrok.io"

        domain = (
            settings.SITE_URL
            if settings.FRESHBOOKS_ENV == "production"
            else ngrok_local_url
        )
        return domain

    @staticmethod
    def get_auth_url():
        redirect_uri = (
            f"{FreshbooksService.get_domain()}{reverse('timary:accounting_redirect')}"
        )

        url = (
            f"https://auth.freshbooks.com/oauth/authorize/?response_type=code&redirect_uri={redirect_uri}"
            f"&client_id={settings.FRESHBOOKS_CLIENT_ID}"
        )
        return url, "freshbooks"

    @staticmethod
    def get_auth_tokens(request):
        redirect_uri = (
            f"{FreshbooksService.get_domain()}{reverse('timary:accounting_redirect')}"
        )
        if "code" in request.GET:
            auth_code = request.GET.get("code")
            auth_request = requests.post(
                "https://api.freshbooks.com/auth/oauth/token",
                headers={
                    "Content-Type": "application/json",
                },
                json={
                    "client_id": settings.FRESHBOOKS_CLIENT_ID,
                    "client_secret": settings.FRESHBOOKS_SECRET_KEY,
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
            try:
                FreshbooksService.get_current_user(
                    request.user, response["access_token"]
                )
            except AccountingError as ae:
                raise AccountingError(
                    user=request.user, requests_response=ae.requests_response
                )
            request.user.save()
            return response["access_token"]
        return None

    @staticmethod
    def get_refreshed_tokens(user):
        redirect_uri = (
            f"{FreshbooksService.get_domain()}{reverse('timary:accounting_redirect')}?"
        )
        auth_request = requests.post(
            "https://api.freshbooks.com/auth/oauth/token",
            headers={
                "Content-Type": "application/json",
            },
            json={
                "client_id": settings.FRESHBOOKS_CLIENT_ID,
                "client_secret": settings.FRESHBOOKS_SECRET_KEY,
                "grant_type": "refresh_token",
                "refresh_token": user.accounting_refresh_token,
                "redirect_uri": redirect_uri,
            },
        )
        if not auth_request.ok:
            raise AccountingError(user=user, requests_response=auth_request)
        response = auth_request.json()
        user.accounting_refresh_token = response["refresh_token"]
        user.save()
        return response["access_token"]

    @staticmethod
    def get_current_user(user, access_token):
        freshbooks_user_request = requests.get(
            "https://api.freshbooks.com/auth/api/v1/users/me",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Api-Version": "alpha",
                "Content-Type": "application/json",
            },
        )
        if not freshbooks_user_request.ok:
            raise AccountingError(requests_response=freshbooks_user_request)
        freshbooks_user_response = freshbooks_user_request.json()
        freshbooks_user_id = freshbooks_user_response["response"][
            "business_memberships"
        ][0]["business"]["account_id"]

        user.accounting_org_id = freshbooks_user_id
        user.save()

    @staticmethod
    def create_request(auth_token, endpoint, method_type, data=None):
        url = f"https://api.freshbooks.com/{endpoint}"
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
            freshbooks_auth_token = auth_token
        else:
            freshbooks_auth_token = FreshbooksService.get_refreshed_tokens(invoice.user)
        data = {
            "client": {
                "email": invoice.email_recipient,
                "fname": invoice.email_recipient_name.split(" ")[0],
                "lname": invoice.email_recipient_name.split(" ")[1],
            }
        }
        endpoint = f"accounting/account/{invoice.user.accounting_org_id}/users/clients"
        try:
            response = FreshbooksService.create_request(
                freshbooks_auth_token, endpoint, method_type="post", data=data
            )
        except AccountingError as ae:
            raise AccountingError(
                user=invoice.user,
                requests_response=ae.requests_response,
            )
        invoice.accounting_customer_id = response["response"]["result"]["client"]["id"]
        invoice.save()

    @staticmethod
    def create_invoice(sent_invoice, auth_token=None):
        if auth_token:
            freshbooks_auth_token = auth_token
        else:
            freshbooks_auth_token = FreshbooksService.get_refreshed_tokens(
                sent_invoice.user
            )

        today = datetime.date.today()
        today_formatted = today.strftime("%Y-%m-%d")

        data = {
            "invoice": {
                "customerid": sent_invoice.invoice.accounting_customer_id,
                "create_date": today_formatted,
                "status": 2,
                "lines": [
                    {
                        "type": "0",
                        "name": "Consulting",
                        "description": f"{sent_invoice.user.get_full_name()} - Services",
                        "qty": "1",
                        "amount": {
                            "amount": float(sent_invoice.total_price),
                            "currency_code": "USD",
                        },
                    }
                ],
            }
        }
        endpoint = f"accounting/account/{sent_invoice.user.accounting_org_id}/invoices/invoices"
        try:
            response = FreshbooksService.create_request(
                freshbooks_auth_token, endpoint, method_type="post", data=data
            )
        except AccountingError as ae:
            raise AccountingError(
                user=sent_invoice.user,
                requests_response=ae.requests_response,
            )

        sent_invoice.accounting_invoice_id = response["response"]["result"]["invoice"][
            "id"
        ]
        sent_invoice.save()

        data = {
            "payment": {
                "invoiceid": sent_invoice.accounting_invoice_id,
                "amount": {
                    "amount": float(sent_invoice.total_price),
                },
                "date": today_formatted,
                "type": "credit",
            }
        }
        endpoint = f"accounting/account/{sent_invoice.user.accounting_org_id}/payments/payments"
        try:
            FreshbooksService.create_request(
                freshbooks_auth_token, endpoint, method_type="post", data=data
            )
        except AccountingError as ae:
            raise AccountingError(
                user=sent_invoice.user,
                requests_response=ae.requests_response,
            )
