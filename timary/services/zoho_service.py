import datetime
import json
import urllib.parse

import requests
from django.conf import settings
from django.urls import reverse

from timary.custom_errors import AccountingError


class ZohoService:
    @staticmethod
    def get_auth_url():
        client_redirect = f"{settings.SITE_URL}{reverse('timary:zoho_redirect')}"
        auth_url = (
            f"https://accounts.zoho.com/oauth/v2/auth?scope=ZohoInvoice.settings.CREATE,ZohoInvoice.settings.READ,"
            f"ZohoInvoice.invoices.CREATE,"
            f"ZohoInvoice.invoices.READ,ZohoInvoice.invoices.UPDATE,ZohoInvoice.contacts.Create,"
            f"ZohoInvoice.contacts.UPDATE,ZohoInvoice.customerpayments.Create,ZohoInvoice.customerpayments.UPDATE"
            f"&client_id={settings.ZOHO_CLIENT_ID}&state=testing&response_type=code&redirect_uri="
            f"{client_redirect}&access_type=offline"
        )
        return auth_url

    @staticmethod
    def get_auth_tokens(request):
        client_redirect = f"{settings.SITE_URL}{reverse('timary:zoho_redirect')}"
        if "code" in request.GET:
            auth_code = request.GET.get("code")

            auth_request = requests.post(
                f"https://accounts.zoho.com/oauth/v2/token?code={auth_code}"
                f"&client_id={settings.ZOHO_CLIENT_ID}&client_secret={settings.ZOHO_SECRET_KEY}"
                f"&redirect_uri={client_redirect}&grant_type=authorization_code"
            )
            if auth_request.status_code != requests.codes.ok:
                raise AccountingError(
                    user_id=request.user.id, requests_response=auth_request
                )
            response = auth_request.json()
            if "refresh_token" in response:
                request.user.zoho_refresh_token = response["refresh_token"]
                request.user.save()
            return response["access_token"]
        return None

    @staticmethod
    def get_refreshed_tokens(user):
        client_redirect = f"{settings.SITE_URL}{reverse('timary:zoho_redirect')}"
        refresh_response = requests.post(
            f"https://accounts.zoho.com/oauth/v2/token?refresh_token={user.zoho_refresh_token}"
            f"&client_id={settings.ZOHO_CLIENT_ID}&client_secret={settings.ZOHO_SECRET_KEY}"
            f"&redirect_uri={client_redirect}&grant_type=refresh_token"
        )
        if refresh_response.status_code != requests.codes.ok:
            raise AccountingError(user_id=user.id, requests_response=refresh_response)
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
            if response.status_code != requests.codes.ok:
                raise AccountingError(requests_response=response)
            return response.json()
        return None

    @staticmethod
    def get_organization_id(user, access_token):
        zoho_org_request = requests.get(
            "https://invoice.zoho.com/api/v3/organizations",
            headers={"Authorization": f"Zoho-oauthtoken {access_token}"},
        )
        zoho_org_request.raise_for_status()
        zoho_org_response = zoho_org_request.json()
        if zoho_org_response["message"] == "success":
            zoho_org_id = zoho_org_response["organizations"][0]["organization_id"]
            user.zoho_organization_id = zoho_org_id
            user.save()

    @staticmethod
    def create_customer(invoice):
        try:
            zoho_auth_token = ZohoService.get_refreshed_tokens(invoice.user)
        except AccountingError as ae:
            ae.log()
            return

        recipient_name = invoice.email_recipient_name.split(" ")
        data = {
            "contact_name": invoice.email_recipient_name,
            "email": invoice.email_recipient,
            "contact_persons": [
                {
                    "first_name": recipient_name[0],
                    "last_name": recipient_name[1],
                    "email": invoice.email_recipient,
                    "is_primary_contact": True,
                }
            ],
        }
        try:
            response = ZohoService.create_request(
                zoho_auth_token,
                invoice.user.zoho_organization_id,
                "contacts",
                "post",
                data=data,
            )
        except AccountingError as ae:
            accounting_error = AccountingError(
                user_id=invoice.user.id, requests_response=ae.requests_response
            )
            accounting_error.log()
            return
        invoice.zoho_contact_id = response["contact"]["contact_id"]
        invoice.zoho_contact_persons_id = response["contact"]["contact_persons"][0][
            "contact_person_id"
        ]
        invoice.save()

    @staticmethod
    def create_invoice(sent_invoice):
        try:
            zoho_auth_token = ZohoService.get_refreshed_tokens(sent_invoice.user)
        except AccountingError as ae:
            ae.log()
            return

        today = datetime.date.today() + datetime.timedelta(days=1)
        today_formatted = today.strftime("%Y-%m-%d")

        # Generate item
        data = {
            "name": f"{sent_invoice.user.first_name} services on {today_formatted} for {sent_invoice.invoice.title}",
            "rate": sent_invoice.total_price,
        }
        try:
            item_request = ZohoService.create_request(
                zoho_auth_token,
                sent_invoice.user.zoho_organization_id,
                "items",
                "post",
                data=data,
            )
        except AccountingError as ae:
            accounting_error = AccountingError(
                user_id=sent_invoice.user.id, requests_response=ae.requests_response
            )
            accounting_error.log()
            return
        item_id = item_request["item"]["item_id"]

        # Mark line item as active
        try:
            ZohoService.create_request(
                zoho_auth_token,
                sent_invoice.user.zoho_organization_id,
                f"items/{item_id}/active",
                "post",
            )
        except AccountingError as ae:
            accounting_error = AccountingError(
                user_id=sent_invoice.user.id, requests_response=ae.requests_response
            )
            accounting_error.log()
            return

        # Generate invoice
        data = {
            "customer_id": sent_invoice.invoice.zoho_contact_id,
            "date": today_formatted,
            "line_items": [
                {
                    "item_id": item_id,
                    "rate": int(sent_invoice.total_price),
                    "quantity": 1,
                    "item_total": int(sent_invoice.total_price),
                }
            ],
        }
        try:
            response = ZohoService.create_request(
                zoho_auth_token,
                sent_invoice.user.zoho_organization_id,
                "invoices",
                "post",
                data=data,
            )
        except AccountingError as ae:
            accounting_error = AccountingError(
                user_id=sent_invoice.user.id, requests_response=ae.requests_response
            )
            accounting_error.log()
            return
        sent_invoice.zoho_invoice_id = response["invoice"]["invoice_id"]
        sent_invoice.save()

        # Generate payment for invoice
        data = {
            "customer_id": sent_invoice.invoice.zoho_contact_id,
            "payment_mode": "creditcard",
            "amount": int(sent_invoice.total_price),
            "date": today_formatted,
            "invoices": [
                {
                    "invoice_id": sent_invoice.zoho_invoice_id,
                    "amount_applied": int(sent_invoice.total_price),
                }
            ],
        }
        try:
            ZohoService.create_request(
                zoho_auth_token,
                sent_invoice.user.zoho_organization_id,
                "customerpayments",
                "post",
                data=data,
            )
        except AccountingError as ae:
            accounting_error = AccountingError(
                user_id=sent_invoice.user.id, requests_response=ae.requests_response
            )
            accounting_error.log()
            return
