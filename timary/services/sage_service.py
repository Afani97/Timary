import datetime
import json

import requests
from django.conf import settings
from django.urls import reverse


class SageService:
    @staticmethod
    def get_auth_url():
        client_redirect = f"{settings.SITE_URL}{reverse('timary:sage_redirect')}"
        auth_url = (
            f"https://www.sageone.com/oauth2/auth/central?filter=apiv3.1&client_id={settings.SAGE_CLIENT_ID}"
            f"&response_type=code&redirect_uri={client_redirect}&scopes=full_access&country=us&local=en-US "
        )
        return auth_url

    @staticmethod
    def get_auth_tokens(request):
        if "code" in request.GET:
            auth_code = request.GET.get("code")

            auth_request = requests.post(
                "https://oauth.accounting.sage.com/token",
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "code": auth_code,
                    "client_id": settings.SAGE_CLIENT_ID,
                    "client_secret": settings.SAGE_SECRET_KEY,
                    "grant_type": "authorization_code",
                    "redirect_uri": f"{settings.SITE_URL}{reverse('timary:sage_redirect')}",
                },
            )
            response = auth_request.json()
            request.user.sage_account_id = response["requested_by_id"]
            request.user.sage_refresh_token = response["refresh_token"]
            request.user.save()

    @staticmethod
    def get_refreshed_tokens(user):
        request = requests.post(
            "https://oauth.accounting.sage.com/token",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "client_id": settings.SAGE_CLIENT_ID,
                "client_secret": settings.SAGE_SECRET_KEY,
                "grant_type": "refresh_token",
                "refresh_token": user.sage_refresh_token,
            },
        )
        response = request.json()
        request.raise_for_status()
        user.sage_refresh_token = response["refresh_token"]
        user.save()
        return response["access_token"]

    @staticmethod
    def create_request(auth_token, endpoint, method_type, data=None):
        base_url = "https://api.accounting.sage.com/v3.1"
        url = f"{base_url}/{endpoint}"
        headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
        }
        if method_type == "get":
            response = requests.get(url, headers=headers)
            return response.json()["$items"]
        elif method_type == "post":
            response = requests.post(
                url,
                headers=headers,
                data=json.dumps(data),
            )
            response.raise_for_status()
            return response.json()
        else:
            return None

    @staticmethod
    def create_customer(invoice):
        sage_auth_token = SageService.get_refreshed_tokens(invoice.user)
        data = {
            "contact": {
                "contact_type_ids": ["CUSTOMER"],
                "name": invoice.email_recipient_name,
                "main_contact_person": {
                    "contact_person_type_ids": ["CUSTOMER"],
                    "name": invoice.email_recipient_name,
                    "email": invoice.email_recipient,
                    "is_main_contact": True,
                    "is_preferred_contact": True,
                },
            }
        }
        response = SageService.create_request(
            sage_auth_token,
            "contacts",
            "post",
            data=data,
        )
        invoice.sage_contact_id = response["id"]
        invoice.save()

    @staticmethod
    def create_invoice(sent_invoice):
        sage_auth_token = SageService.get_refreshed_tokens(sent_invoice.user)
        today = datetime.date.today() + datetime.timedelta(days=1)
        today_formatted = today.strftime("%Y-%m-%d")

        # Get Professional Fees Ledger Id
        ledger_response = SageService.create_request(
            sage_auth_token, "ledger_accounts?items_per_page=200", "get"
        )
        ledger_account_id = list(
            filter(
                None,
                [
                    led["id"] if "Professional Fees" in led["displayed_as"] else None
                    for led in ledger_response
                ],
            )
        )[0]

        # Get Sage Bank Account Id
        response = SageService.create_request(sage_auth_token, "bank_accounts", "get")
        bank_account_id = response[0]["id"]

        # Get Tax Rate For User
        response = SageService.create_request(
            sage_auth_token,
            "tax_rates?attributes=name,percentage&items_per_page=200",
            "get",
        )
        no_tax_id = response[0]["id"]

        # Generate invoice
        data = {
            "sales_invoice": {
                "contact_id": sent_invoice.invoice.sage_contact_id,
                "date": today_formatted,
                "invoice_lines": [
                    {
                        "description": f"Invoice for {sent_invoice.invoice.email_recipient_name}",
                        "ledger_account_id": ledger_account_id,
                        "quantity": "1",
                        "tax_rate_id": no_tax_id,
                        "unit_price": str(float(sent_invoice.total_price)),
                    }
                ],
            }
        }

        response = SageService.create_request(
            sage_auth_token,
            "sales_invoices",
            "post",
            data=data,
        )
        sent_invoice.sage_invoice_id = response["id"]
        sent_invoice.save()

        # Generate payment for invoice
        data = {
            "contact_payment": {
                "transaction_type_id": "CUSTOMER_RECEIPT",
                "payment_method_id": "CREDIT_DEBIT",
                "contact_id": sent_invoice.invoice.sage_contact_id,
                "bank_account_id": bank_account_id,
                "date": today_formatted,
                "total_amount": str(float(sent_invoice.total_price)),
                "allocated_artefacts": [
                    {
                        "artefact_id": sent_invoice.sage_invoice_id,
                        "amount": str(float(sent_invoice.total_price)),
                    }
                ],
            }
        }

        response = SageService.create_request(
            sage_auth_token,
            "contact_payments",
            "post",
            data=data,
        )