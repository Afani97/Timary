import datetime
import json

import requests
from django.conf import settings
from django.urls import reverse
from freshbooks import Client

from timary.models import FreshbooksOAuth


class FreshbookService:
    access_token = None
    refresh_token = None

    @staticmethod
    def get_domain():
        ngrok_local_url = "https://7bf5-71-87-212-255.ngrok.io"

        domain = (
            settings.SITE_URL
            if settings.FRESHBOOKS_ENV == "production"
            else ngrok_local_url
        )
        return domain

    @staticmethod
    def get_client():
        freshbooks_client = Client(
            client_id=settings.FRESHBOOKS_CLIENT_ID,
            client_secret=settings.FRESHBOOKS_SECRET_KEY,
            redirect_uri=f"{FreshbookService.get_domain()}{reverse('timary:freshbooks_redirect')}",
        )
        return freshbooks_client

    @staticmethod
    def get_auth_url():
        freshbooks_client = Client(
            client_id=settings.FRESHBOOKS_CLIENT_ID,
            client_secret=settings.FRESHBOOKS_SECRET_KEY,
            redirect_uri=f"{FreshbookService.get_domain()}{reverse('timary:freshbooks_redirect')}",
        )

        return freshbooks_client.get_auth_request_url()

    @staticmethod
    def get_refreshed_tokens():
        freshbooks_oauth_object = FreshbooksOAuth.objects.first()

        auth_client = FreshbookService.get_client()
        auth_client.refresh_access_token(
            refresh_token=freshbooks_oauth_object.refresh_token
        )

        FreshbookService.access_token = auth_client.access_token
        FreshbookService.refresh_token = auth_client.refresh_token

        freshbooks_oauth_object.refresh_token = auth_client.refresh_token
        freshbooks_oauth_object.save()
        return auth_client.access_token

    @staticmethod
    def get_auth_tokens(request):
        auth_code = request.GET.get("code")
        client = FreshbookService.get_client()
        auth_tokens = client.get_access_token(auth_code)

        current_freshbooks_user = client.current_user()
        freshbooks_account_id = current_freshbooks_user.data["business_memberships"][0][
            "business"
        ]["account_id"]

        request.user.freshbooks_account_id = freshbooks_account_id
        request.user.save()

        FreshbookService.access_token = auth_tokens.access_token
        FreshbookService.refresh_token = auth_tokens.refresh_token

        if FreshbooksOAuth.objects.count() == 0:
            # There should only be one Freshbooks refresh token in db.
            FreshbooksOAuth.objects.create(refresh_token=auth_tokens.refresh_token)

    @staticmethod
    def create_request(endpoint, method_type, data=None):
        url = f"https://api.freshbooks.com/{endpoint}"
        headers = {
            "Authorization": f"Bearer {FreshbookService.get_refreshed_tokens()}",
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
        response = FreshbookService.create_request(
            endpoint, method_type="post", data=data
        )
        invoice.freshbooks_client_id = response["response"]["result"]["client"]["id"]
        invoice.save()

    @staticmethod
    def create_invoice(sent_invoice):
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
        response = FreshbookService.create_request(
            endpoint, method_type="post", data=data
        )

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
        response = FreshbookService.create_request(
            endpoint, method_type="post", data=data
        )