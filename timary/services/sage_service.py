import datetime
import json

import requests
from django.conf import settings
from django.urls import reverse

from timary.custom_errors import AccountingError
from timary.models import SentInvoice, SingleInvoice


class SageService:
    @staticmethod
    def get_auth_url():
        client_redirect = f"{settings.SITE_URL}{reverse('timary:accounting_redirect')}"
        auth_url = (
            f"https://www.sageone.com/oauth2/auth/central?filter=apiv3.1&client_id={settings.SAGE_CLIENT_ID}"
            f"&response_type=code&redirect_uri={client_redirect}&scopes=full_access&country=us&local=en-US "
        )
        return auth_url, "sage"

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
                    "redirect_uri": f"{settings.SITE_URL}{reverse('timary:accounting_redirect')}",
                },
            )
            if not auth_request.ok:
                raise AccountingError(
                    user=request.user,
                    requests_response=auth_request,
                )
            response = auth_request.json()
            if "refresh_token" not in response:
                raise AccountingError(
                    user=request.user,
                    requests_response=auth_request,
                )
            request.user.accounting_org_id = response["requested_by_id"]
            request.user.accounting_refresh_token = response["refresh_token"]
            request.user.save()
            return response["refresh_token"]
        return None

    @staticmethod
    def get_refreshed_tokens(user):
        refresh_response = requests.post(
            "https://oauth.accounting.sage.com/token",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "client_id": settings.SAGE_CLIENT_ID,
                "client_secret": settings.SAGE_SECRET_KEY,
                "grant_type": "refresh_token",
                "refresh_token": user.accounting_refresh_token,
            },
        )
        if not refresh_response.ok:
            raise AccountingError(user=user, requests_response=refresh_response)
        response = refresh_response.json()
        user.accounting_refresh_token = response["refresh_token"]
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
            if not response.ok:
                raise AccountingError(requests_response=response)
            return response.json()["$items"]
        elif method_type == "post":
            response = requests.post(
                url,
                headers=headers,
                data=json.dumps(data),
            )
            if not response.ok:
                raise AccountingError(requests_response=response)
            return response.json()
        elif method_type == "delete":
            response = requests.delete(url, headers=headers)
            if not response.ok:
                raise AccountingError(requests_response=response)
            return response.json()
        return None

    @staticmethod
    def create_customer(invoice, auth_token=None):
        if auth_token:
            sage_auth_token = auth_token
        else:
            sage_auth_token = SageService.get_refreshed_tokens(invoice.user)
        data = {
            "contact": {
                "contact_type_ids": ["CUSTOMER"],
                "name": invoice.client_name,
                "main_contact_person": {
                    "contact_person_type_ids": ["CUSTOMER"],
                    "name": invoice.client_name,
                    "email": invoice.client_email,
                    "is_main_contact": True,
                    "is_preferred_contact": True,
                },
            }
        }
        try:
            response = SageService.create_request(
                sage_auth_token,
                "contacts",
                "post",
                data=data,
            )
        except AccountingError as ae:
            raise AccountingError(
                user=invoice.user,
                requests_response=ae.requests_response,
            )
        invoice.accounting_customer_id = response["id"]
        invoice.save()

    @staticmethod
    def create_invoice(sent_invoice, auth_token=None):
        if auth_token:
            sage_auth_token = auth_token
        else:
            sage_auth_token = SageService.get_refreshed_tokens(sent_invoice.user)
        today = datetime.date.today() + datetime.timedelta(days=1)
        today_formatted = today.strftime("%Y-%m-%d")

        # Get Professional Fees Ledger Id
        try:
            ledger_response = SageService.create_request(
                sage_auth_token, "ledger_accounts?items_per_page=200", "get"
            )
        except AccountingError as ae:
            raise AccountingError(
                user=sent_invoice.user,
                requests_response=ae.requests_response,
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
        try:
            response = SageService.create_request(
                sage_auth_token, "bank_accounts", "get"
            )
        except AccountingError as ae:
            raise AccountingError(
                user=sent_invoice.user,
                requests_response=ae.requests_response,
            )
        bank_account_id = response[0]["id"]

        # Get Tax Rate For User
        try:
            response = SageService.create_request(
                sage_auth_token,
                "tax_rates?attributes=name,percentage&items_per_page=200",
                "get",
            )
        except AccountingError as ae:
            raise AccountingError(
                user=sent_invoice.user,
                requests_response=ae.requests_response,
            )
        no_tax_id = response[0]["id"]

        # Generate invoice
        data = {
            "sales_invoice": {
                "date": today_formatted,
                "invoice_lines": [
                    {
                        "ledger_account_id": ledger_account_id,
                        "quantity": "1",
                        "tax_rate_id": no_tax_id,
                        "unit_price": str(float(sent_invoice.total_price)),
                    }
                ],
            }
        }
        if isinstance(sent_invoice, SentInvoice):
            data["sales_invoice"].update(
                {
                    "contact_id": sent_invoice.invoice.accounting_customer_id,
                }
            )
            data["sales_invoice"]["invoice_lines"][0].update(
                {"description": f"Invoice for {sent_invoice.invoice.client_name}"}
            )
        elif isinstance(sent_invoice, SingleInvoice):
            data["sales_invoice"].update(
                {
                    "contact_id": sent_invoice.accounting_customer_id,
                }
            )
            data["sales_invoice"]["invoice_lines"][0].update(
                {"description": f"Invoice for {sent_invoice.client_name}"}
            )

        try:
            response = SageService.create_request(
                sage_auth_token,
                "sales_invoices",
                "post",
                data=data,
            )
        except AccountingError as ae:
            raise AccountingError(
                user=sent_invoice.user,
                requests_response=ae.requests_response,
            )
        sent_invoice.accounting_invoice_id = response["id"]
        sent_invoice.save()

        # Generate payment for invoice
        data = {
            "contact_payment": {
                "transaction_type_id": "CUSTOMER_RECEIPT",
                "payment_method_id": "CREDIT_DEBIT",
                "bank_account_id": bank_account_id,
                "date": today_formatted,
                "total_amount": str(float(sent_invoice.total_price)),
                "allocated_artefacts": [
                    {
                        "artefact_id": sent_invoice.accounting_invoice_id,
                        "amount": str(float(sent_invoice.total_price)),
                    }
                ],
            }
        }
        if isinstance(sent_invoice, SentInvoice):
            data["contact_payment"].update(
                {
                    "contact_id": sent_invoice.invoice.accounting_customer_id,
                }
            )
        elif isinstance(sent_invoice, SingleInvoice):
            data["sales_invoice"].update(
                {
                    "contact_id": sent_invoice.accounting_customer_id,
                }
            )

        try:
            SageService.create_request(
                sage_auth_token,
                "contact_payments",
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
        sage_auth_token = SageService.get_refreshed_tokens(user)
        data = {
            "contact": {
                "contact_type_ids": ["CUSTOMER"],
                "name": "Bob Smith",
                "main_contact_person": {
                    "contact_person_type_ids": ["CUSTOMER"],
                    "name": "Bob Smith",
                    "email": "bob@example.com",
                    "is_main_contact": True,
                    "is_preferred_contact": True,
                },
            }
        }
        try:
            response = SageService.create_request(
                sage_auth_token,
                "contacts",
                "post",
                data=data,
            )
        except AccountingError as ae:
            raise AccountingError(
                user=user,
                requests_response=ae.requests_response,
            )

        customer_id = response["id"]

        try:
            SageService.create_request(
                sage_auth_token,
                f"contacts/{customer_id}",
                "delete",
                data=data,
            )
        except AccountingError as ae:
            raise AccountingError(
                user=user,
                requests_response=ae.requests_response,
            )
