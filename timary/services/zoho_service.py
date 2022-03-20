import datetime
import json
import urllib.parse

import requests
from django.conf import settings
from django.urls import reverse

from timary.models import ZohoOAuth, create_new_ref_number


class ZohoService:
    access_token = None
    refresh_token = None

    @staticmethod
    def get_auth_url():
        client_redirect = f"{settings.SITE_URL}{reverse('timary:zoho_redirect')}"
        auth_url = (
            f"https://accounts.zoho.com/oauth/v2/auth?scope=ZohoInvoice.settings.READ,ZohoInvoice.invoices.CREATE,"
            f"ZohoInvoice.invoices.READ,ZohoInvoice.invoices.UPDATE,ZohoInvoice.contacts.Create,"
            f"ZohoInvoice.contacts.UPDATE,ZohoInvoice.customerpayments.Create,ZohoInvoice.customerpayments.UPDATE "
            f"&client_id={settings.ZOHO_CLIENT_ID}&state=testing&response_type=code&redirect_uri="
            f"{client_redirect}&access_type=offline"
        )
        return auth_url

    @staticmethod
    def get_auth_tokens(request):
        client_redirect = f"{settings.SITE_URL}{reverse('timary:zoho_redirect')}"
        if "code" in request.GET:
            auth_code = request.GET.get("code")

            request = requests.post(
                f"https://accounts.zoho.com/oauth/v2/token?code={auth_code}"
                f"&client_id={settings.ZOHO_CLIENT_ID}&client_secret={settings.ZOHO_SECRET_KEY}"
                f"&redirect_uri={client_redirect}&grant_type=authorization_code"
            )
            response = request.json()
            ZohoService.refresh_token = response["refresh_token"]
            ZohoService.access_token = response["access_token"]
            if ZohoOAuth.objects.count() == 0:
                ZohoOAuth.objects.create(refresh_token=response["refresh_token"])
            return ZohoService.access_token
        return None

    @staticmethod
    def get_refreshed_tokens():
        client_redirect = f"{settings.SITE_URL}{reverse('timary:zoho_redirect')}"
        zoho_oauth_object = ZohoOAuth.objects.first()
        request = requests.post(
            f"https://accounts.zoho.com/oauth/v2/token?refresh_token={zoho_oauth_object.refresh_token}"
            f"&client_id={settings.ZOHO_CLIENT_ID}&client_secret={settings.ZOHO_SECRET_KEY}"
            f"&redirect_uri={client_redirect}&grant_type=refresh_token"
        )
        request.raise_for_status()
        response = request.json()
        return response["access_token"]

    @staticmethod
    def create_request(org_id, endpoint, method_type, data=None):
        base_url = "https://invoice.zoho.com/api/v3"
        url = f"{base_url}/{endpoint}?organization_id={org_id}"
        auth_token = ZohoService.get_refreshed_tokens()
        headers = {
            "Authorization": f"Zoho-oauthtoken {auth_token}",
            "Content-Type": "application/json",
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
            response.raise_for_status()
            return response.json()
        else:
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
        response = ZohoService.create_request(
            invoice.user.zoho_organization_id, "contacts", "post", data=data
        )
        invoice.zoho_contact_id = response["contact"]["contact_id"]
        invoice.zoho_contact_persons_id = response["contact"]["contact_persons"][0][
            "contact_person_id"
        ]
        invoice.save()

    @staticmethod
    def create_invoice(sent_invoice):
        # Generate invoice
        today = datetime.date.today()
        today_formatted = today.strftime("%Y-%m-%d")
        data = {
            "customer_id": 3159267000000077029,
            "date": today_formatted,
            "line_items": [
                {
                    "item_id": int(create_new_ref_number()),
                    "rate": int(sent_invoice.total_price),
                    "quantity": 1,
                    "item_total": int(sent_invoice.total_price),
                }
            ],
        }
        response = ZohoService.create_request(
            sent_invoice.user.zoho_organization_id,
            "invoices",
            "post",
            data=data,
        )
        sent_invoice.zoho_invoice_id = response["invoice"]["invoice_id"]
        sent_invoice.save()

        # Generate payment for invoice
        data = {
            "customer_id": str(sent_invoice.invoice.zoho_contact_id),
            "payment_mode": "creditcard",
            "amount": int(sent_invoice.total_price),
            "date": today_formatted,
            "invoices": [
                {
                    "invoice_id": str(sent_invoice.zoho_invoice_id),
                    "amount_applied": int(sent_invoice.total_price),
                }
            ],
        }
        response = ZohoService.create_request(
            sent_invoice.user.zoho_organization_id,
            "customerpayments",
            "post",
            data=data,
        )
