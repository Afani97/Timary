from unittest.mock import patch

from django.urls import reverse
from requests import Response

from timary.custom_errors import AccountingError
from timary.tests.factories import ClientFactory, UserFactory
from timary.tests.test_views.basetest import BaseTest


class TestClients(BaseTest):
    def setUp(self) -> None:
        super().setUp()

        self.user = UserFactory(accounting_org="Zoho", accounting_org_id="abc123")
        self.client.force_login(self.user)

    @patch("timary.models.Client.sync_customer", return_value=None)
    @patch("timary.services.accounting_service.AccountingService.get_customers")
    def test_fetch_clients_from_accounting_service(
        self, get_customers_mock, sync_client_mock
    ):
        get_customers_mock.return_value = [
            {
                "accounting_customer_id": "abc123",
                "name": "Bob Smith",
                "email": "bob@smith.com",
            }
        ]
        response = self.client.get(reverse("timary:get_accounting_clients"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user.my_clients.count(), 1)

    @patch("timary.models.Client.sync_customer", return_value=None)
    @patch("timary.services.accounting_service.AccountingService.get_customers")
    def test_fetch_new_clients_from_accounting_service(
        self, get_customers_mock, sync_client_mock
    ):
        ClientFactory(user=self.user, accounting_customer_id="abc124")
        get_customers_mock.return_value = [
            {
                "accounting_customer_id": "abc123",
                "name": "Bob Smith",
                "email": "bob@smith.com",
            },
            {
                "accounting_customer_id": "abc124",
                "name": "Bob Smith",
                "email": "bob@smith.com",
            },
        ]
        response = self.client.get(reverse("timary:get_accounting_clients"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user.my_clients.count(), 2)

    @patch(
        "timary.services.accounting_service.AccountingService.get_customers",
    )
    def test_error_fetch_client_from_accounting_service(self, get_customers_mock):
        class FakeResponse(Response):
            def json(self, **kwargs):
                return {"code": 3062, "message": "Error"}

        get_customers_mock.side_effect = AccountingError(
            user=self.user, requests_response=FakeResponse()
        )
        response = self.client.get(reverse("timary:get_accounting_clients"))

        self.assertEqual(self.user.my_clients.count(), 0)
        self.assertIn("Unable to sync clients from Zoho", str(response.headers))
