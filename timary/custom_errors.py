import sys

from django.conf import settings
from requests import Response

from timary.services.email_service import EmailService


class AccountingError(Exception):
    def __init__(
        self, service="Accounting", user_id=None, requests_response: Response = None
    ):
        self.service = service
        self.user_id = user_id
        self.requests_response = requests_response

    def __str__(self):
        return f"AccountingError, {self.requests_response.reason}"

    def log(self, initial_sync=False):
        from timary.models import User

        user = User.objects.get(id=self.user_id)
        if initial_sync:
            # Remove the account ids if an error occurs after we get their integration tokens,
            # that way it gives user another try to sync.
            if self.service == "Quickbooks":
                user.quickbooks_realm_id = None
                user.quickbooks_refresh_token = None
            elif self.service == "Freshbooks":
                user.freshbooks_account_id = None
                user.freshbooks_refresh_token = None
            elif self.service == "Zoho":
                user.zoho_organization_id = None
                user.zoho_refresh_token = None
            elif self.service == "Sage":
                user.sage_account_id = None
                user.sage_refresh_token = None
            elif self.service == "Xero":
                user.xero_tenant_id = None
                user.xero_refresh_token = None
            user.save()
        print(
            f"{self.service=}, "
            f"{self.user_id=}, "
            f"{self.requests_response.status_code=}, "
            f"{self.requests_response.reason=}, "
            f"{self.requests_response.json()=}",
            file=sys.stderr,
        )

        EmailService.send_plain(
            "Oops, we ran into an error at Timary",
            f"""
Hello {user.first_name},

It looks like we encountered when trying to sync with your accounting service.

Please allow us to resolve this issue within 24-48 hours.
We will reach out to you if we cannot resolve it on our side.

Please do not hesitate to reach out to us for any questions you have to: {settings.EMAIL_HOST_USER}

Regards,
Timary Team
            """,
            user.email,
        )
