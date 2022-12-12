import sys

from django.conf import settings
from requests import Response

from timary.services.email_service import EmailService


class AccountingError(Exception):
    def __init__(self, user=None, requests_response: Response = None):
        if user:
            self.service = user.accounting_org
            self.user_id = user.id
        self.requests_response = requests_response

    def __str__(self):
        return f"AccountingError, {self.requests_response.reason}"

    def log(self, initial_sync=False):
        self.initial_sync = initial_sync
        from timary.models import User

        user = User.objects.get(id=self.user_id)
        if initial_sync:
            # Remove the account ids if an error occurs after we get their integration tokens,
            # that way it gives user another try to sync.
            user.accounting_org = None
            user.accounting_org_id = None
            user.accounting_refresh_token = None
            user.save()

        error_reason = None
        if self.service.lower() == "quickbooks":
            error_reason = self.quickbook_errors(self.requests_response.json())
        elif self.service.lower() == "freshbooks":
            error_reason = self.freshbook_errors(self.requests_response.json())
        elif self.service.lower() == "zoho":
            error_reason = self.zoho_errors(self.requests_response.json())
        elif self.service.lower() == "xero":
            error_reason = self.xero_errors(self.requests_response.json())
        elif self.service.lower() == "sage":
            error_reason = self.sage_errors(self.requests_response.json())

        if not error_reason:
            # Let Sentry catch this error
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

It looks like we encountered when trying to sync with {self.service.title()}.

Please allow us to resolve this issue within 24-48 hours.
We will reach out to you if we cannot resolve it on our side.

Please do not hesitate to reach out to us for any questions you have to: {settings.EMAIL_HOST_USER}

Regards,
Timary Team
            """,
                user.email,
            )

        return error_reason

    def quickbook_errors(self, response):
        # No auth code found in oauth setup.
        if "error" in response and response["error"] == 10 and self.initial_sync:
            return response["message"]

        if "Fault" in response and len(response["Fault"]["Error"]) > 0:
            first_error = response["Fault"]["Error"][0]
            if first_error["code"] == "6240":
                # Duplicate client name found.
                return (
                    "Duplicate client name already found in Quickbooks. "
                    "Please delete contact in Quickbooks and try again."
                )
            if first_error["code"] == "6560":
                # No customer linked with invoice
                return (
                    "Customer not found linked with invoice, please make sure the client "
                    "is synced with Quickbooks first then re-sync this invoice."
                )
            if first_error["code"] == "6190":
                # Customer's Quickbooks account is inactive
                return (
                    "Subscription period has ended or canceled or there was a billing problem. "
                    "You can't add data to QuickBooks Online Plus because your trial or subscription period ended, "
                    "you canceled your subscription, or there was a billing problem."
                )

    def freshbook_errors(self, response):
        # Freshbooks account is not active anymore
        if (
            "response" in response
            and response["response"]["errors"][0]["errno"] == 1042
        ):
            return "Your Freshbooks account appears to be inactive. Please re-activate to sync your invoices."

    def zoho_errors(self, response):
        # Zoho might not return a refresh token when adding Zoho again as a service.
        if "refresh_token" not in response and self.initial_sync:
            return "Please un-authorize Timary in your Zoho app sessions and try again."

        # A client with same name is already found in Zoho client list.
        if response["code"] == 3062:
            return response["message"]

    def xero_errors(self, response):
        # Custom Xero error to catch a failed oauth connect. Usually means no organization was selected.
        if "error" in response and response["error"] == 10:
            return response["message"]

    def sage_errors(self, response):
        if len(response) > 0:
            first_error = response[0]
            # Sage account is not active anymore.
            if first_error["$dataCode"] == "AuthorizationFailure":
                return "Your Sage account seems to be in-active. Please re-activate to sync your invoices."
