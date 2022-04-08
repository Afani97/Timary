import sys

from requests import Response


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
        print(
            f"{self.service=}, "
            f"{self.user_id=}, "
            f"{self.requests_response.status_code=}, "
            f"{self.requests_response.reason=}, "
            f"{self.requests_response.json()=}",
            file=sys.stderr,
        )
