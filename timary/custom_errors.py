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

    def log(self):
        from timary.models import User

        print(
            f"{self.service=}, "
            f"{self.user_id=}, "
            f"{self.requests_response.status_code=}, "
            f"{self.requests_response.reason=}, "
            f"{self.requests_response.json()=}",
            file=sys.stderr,
        )

        user = User.objects.get(id=self.user_id)
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

    @staticmethod
    def log_errors(user, errors):

        for error in errors:
            print(
                f"{error.service=}, "
                f"{error.user_id=}, "
                f"{error.requests_response.status_code=}, "
                f"{error.requests_response.reason=}, "
                f"{error.requests_response.json()=}",
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
