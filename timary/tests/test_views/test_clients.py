from unittest.mock import patch

from django.urls import reverse
from requests import Response

from timary.custom_errors import AccountingError
from timary.models import Client
from timary.tests.factories import ClientFactory, IntervalInvoiceFactory, UserFactory
from timary.tests.test_views.basetest import BaseTest


class TestClients(BaseTest):
    def setUp(self) -> None:
        super().setUp()

        self.user = UserFactory(accounting_org="Zoho", accounting_org_id="abc123")
        self.client.force_login(self.user)

    @patch("timary.models.Client.sync_customer", return_value=None)
    def test_create_client(self, sync_customer):
        response = self.client.post(
            reverse("timary:create_client"),
            {
                "name": "John Smith",
                "email": "john@smith.com",
            },
        )
        self.assertTemplateUsed(response, "clients/_client.html")
        self.assertEqual(Client.objects.count(), 1)

    @patch("timary.models.Client.sync_customer", return_value=None)
    def test_create_client_error(self, sync_customer):
        response = self.client.post(
            reverse("timary:create_client"),
            {
                "name": "John Smith",
                "email": "john@smith",
            },
        )
        self.assertTemplateUsed(response, "clients/_form.html")
        self.assertEqual(Client.objects.count(), 0)

    def test_update_client(self):
        fake_client = ClientFactory(user=self.user)
        response = self.client.post(
            reverse("timary:update_client", kwargs={"client_id": fake_client.id}),
            {
                "name": "John Smith",
                "email": "john@smith.com",
            },
        )
        self.assertTemplateUsed(response, "clients/_client.html")
        fake_client.refresh_from_db()
        self.assertEqual(fake_client.name, "John Smith")

    def test_update_client_error(self):
        fake_client = ClientFactory(user=self.user)
        response = self.client.post(
            reverse("timary:update_client", kwargs={"client_id": fake_client.id}),
            {
                "name": "John Smith",
                "email": "john@smith",
            },
        )
        self.assertTemplateUsed(response, "clients/_form.html")
        fake_client.refresh_from_db()
        self.assertIn("Enter a valid email address.", response.content.decode())

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

    def test_delete_client(self):
        fake_client = ClientFactory(user=self.user)
        response = self.client.delete(
            reverse("timary:delete_client", kwargs={"client_id": fake_client.id})
        )
        self.assertIn(f"Successfully removed {fake_client.name}", str(response.headers))
        with self.assertRaises(Client.DoesNotExist):
            fake_client.refresh_from_db()

    def test_cannot_delete_client(self):
        fake_client = ClientFactory(user=self.user)
        IntervalInvoiceFactory(client=fake_client)
        response = self.client.delete(
            reverse("timary:delete_client", kwargs={"client_id": fake_client.id})
        )
        self.assertIn(
            f"{fake_client.name} is associated with invoices, cannot remove.",
            str(response.headers),
        )
        fake_client.refresh_from_db()
        self.assertIsNotNone(fake_client)
