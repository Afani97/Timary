import datetime
import json

import requests
from django.conf import settings
from django.urls import reverse

from timary.custom_errors import AccountingError


class FreshbookService:
    @staticmethod
    def get_domain():
        ngrok_local_url = "https://c1e1-71-87-212-255.ngrok.io"

        domain = (
            settings.SITE_URL
            if settings.FRESHBOOKS_ENV == "production"
            else ngrok_local_url
        )
        return domain

    @staticmethod
    def get_auth_url():
        redirect_uri = (
            f"{FreshbookService.get_domain()}{reverse('timary:freshbooks_redirect')}"
        )

        return (
            f"https://auth.freshbooks.com/oauth/authorize/?response_type=code&redirect_uri={redirect_uri}"
            f"&client_id={settings.FRESHBOOKS_CLIENT_ID}"
        )

    @staticmethod
    def get_auth_tokens(request):
        redirect_uri = (
            f"{FreshbookService.get_domain()}{reverse('timary:freshbooks_redirect')}"
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
            if auth_request.status_code != requests.codes.ok:
                raise AccountingError(
                    user_id=request.user.id, requests_response=auth_request
                )
            response = auth_request.json()
            request.user.freshbooks_refresh_token = response["refresh_token"]
            request.user.save()
            return response["access_token"]

    @staticmethod
    def get_refreshed_tokens(user):
        redirect_uri = (
            f"{FreshbookService.get_domain()}{reverse('timary:freshbooks_redirect')}"
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
                "refresh_token": user.freshbooks_refresh_token,
                "redirect_uri": redirect_uri,
            },
        )
        if auth_request.status_code != requests.codes.ok:
            raise AccountingError(user_id=user.id, requests_response=auth_request)
        response = auth_request.json()
        user.freshbooks_refresh_token = response["refresh_token"]
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
        freshbooks_user_request.raise_for_status()
        freshbooks_user_response = freshbooks_user_request.json()
        freshbooks_user_id = freshbooks_user_response["response"][
            "business_memberships"
        ][0]["business"]["account_id"]

        user.freshbooks_account_id = freshbooks_user_id
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
            if response.status_code != requests.codes.ok:
                raise AccountingError(requests_response=response)
            return response.json()
        return None

    @staticmethod
    def create_customer(invoice):
        try:
            freshbooks_auth_token = FreshbookService.get_refreshed_tokens(invoice.user)
        except AccountingError as ae:
            ae.log()
            return
        data = {
            "client": {
                "email": invoice.email_recipient,
                "fname": invoice.email_recipient_name.split(" ")[0],
                "lname": invoice.email_recipient_name.split(" ")[1],
            }
        }
        endpoint = (
            f"accounting/account/{invoice.user.freshbooks_account_id}/users/clients"
        )
        try:
            response = FreshbookService.create_request(
                freshbooks_auth_token, endpoint, method_type="post", data=data
            )
        except AccountingError as ae:
            accounting_error = AccountingError(
                user_id=invoice.user.id, requests_response=ae.requests_response
            )
            accounting_error.log()
            return
        invoice.freshbooks_client_id = response["response"]["result"]["client"]["id"]
        invoice.save()

    @staticmethod
    def create_invoice(sent_invoice):
        try:
            freshbooks_auth_token = FreshbookService.get_refreshed_tokens(
                sent_invoice.user
            )
        except AccountingError as ae:
            ae.log()
            return

        today = datetime.date.today()
        today_formatted = today.strftime("%Y-%m-%d")

        data = {
            "invoice": {
                "customerid": sent_invoice.invoice.freshbooks_client_id,
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
        endpoint = f"accounting/account/{sent_invoice.user.freshbooks_account_id}/invoices/invoices"
        try:
            response = FreshbookService.create_request(
                freshbooks_auth_token, endpoint, method_type="post", data=data
            )
        except AccountingError as ae:
            accounting_error = AccountingError(
                user_id=sent_invoice.user.id, requests_response=ae.requests_response
            )
            accounting_error.log()
            return

        sent_invoice.freshbooks_invoice_id = response["response"]["result"]["invoice"][
            "id"
        ]
        sent_invoice.save()

        data = {
            "payment": {
                "invoiceid": sent_invoice.freshbooks_invoice_id,
                "amount": {
                    "amount": float(sent_invoice.total_price),
                },
                "date": today_formatted,
                "type": "credit",
            }
        }
        endpoint = f"accounting/account/{sent_invoice.user.freshbooks_account_id}/payments/payments"
        try:
            FreshbookService.create_request(
                freshbooks_auth_token, endpoint, method_type="post", data=data
            )
        except AccountingError as ae:
            accounting_error = AccountingError(
                user_id=sent_invoice.user.id, requests_response=ae.requests_response
            )
            accounting_error.log()
            return
