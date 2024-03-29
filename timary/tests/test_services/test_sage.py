from django.test import Client, TestCase
from django.test.client import RequestFactory
from httmock import HTTMock, urlmatch
from requests import Response

from timary.custom_errors import AccountingError
from timary.services.sage_service import SageService
from timary.tests.factories import (
    ClientFactory,
    InvoiceFactory,
    SentInvoiceFactory,
    UserFactory,
)


class SageMocks:
    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="oauth.accounting.sage.com",
        path="/token",
        method="POST",
    )
    def sage_oauth_mock(url, request):
        r = Response()
        r.status_code = 200
        r._content = b'{"refresh_token": "abc123", "access_token": "abc123", "requested_by_id": "abc123"}'
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="oauth.accounting.sage.com",
        path="/token",
        method="POST",
    )
    def sage_oauth_error_mock(url, request):
        r = Response()
        r.status_code = 200
        r._content = b"{}"
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="api.accounting.sage.com",
        path="/v3.1/contacts",
        method="POST",
    )
    def sage_customer_mock(url, request):
        r = Response()
        r.status_code = 200
        r._content = b'{"id": "abc123"}'
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="api.accounting.sage.com",
        path="/v3.1/contacts",
        method="POST",
    )
    def sage_error_customer_mock(url, request):
        r = Response()
        r.status_code = 400
        r._content = b"{}"
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="api.accounting.sage.com",
        path="/v3.1/contacts/abc123",
        method="PUT",
    )
    def sage_update_customer_mock(url, request):
        r = Response()
        r.status_code = 200
        r._content = b'{"id": "abc123"}'
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="api.accounting.sage.com",
        path="/v3.1/contacts/abc123",
        method="PUT",
    )
    def sage_error_update_customer_mock(url, request):
        r = Response()
        r.status_code = 400
        r._content = b"{}"
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="api.accounting.sage.com",
        path="/v3.1/ledger_accounts",
        method="GET",
    )
    def sage_invoice_ledger_mock(url, request):
        r = Response()
        r.status_code = 200
        r._content = (
            b'{"$items": [{"id": "abc123", "displayed_as": "Professional Fees"}]}'
        )
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="api.accounting.sage.com",
        path="/v3.1/bank_accounts",
        method="GET",
    )
    def sage_invoice_bank_account_mock(url, request):
        r = Response()
        r.status_code = 200
        r._content = b'{"$items": [{"id": "abc123"}]}'
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="api.accounting.sage.com",
        path="/v3.1/tax_rates",
        method="GET",
    )
    def sage_invoice_tax_rate_mock(url, request):
        r = Response()
        r.status_code = 200
        r._content = b'{"$items": [{"id": "abc123"}]}'
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="api.accounting.sage.com",
        path="/v3.1/sales_invoices",
        method="POST",
    )
    def sage_invoice_mock(url, request):
        r = Response()
        r.status_code = 200
        r._content = b'{"id": "abc123"}'
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="api.accounting.sage.com",
        path="/v3.1/sales_invoices",
        method="POST",
    )
    def sage_error_invoice_mock(url, request):
        r = Response()
        r.status_code = 400
        r._content = b"{}"
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="api.accounting.sage.com",
        path="/v3.1/contact_payments",
        method="POST",
    )
    def sage_payment_mock(url, request):
        r = Response()
        r.status_code = 200
        r._content = b'{"id": "abc123"}'
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="api.accounting.sage.com",
        path="/v3.1/contact_payments",
        method="POST",
    )
    def sage_error_payment_mock(url, request):
        r = Response()
        r.status_code = 400
        r._content = b"{}"
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="api.accounting.sage.com",
        path="/v3.1/contacts",
        method="GET",
    )
    def sage_fetch_customers_mock(url, request):
        r = Response()
        r.status_code = 200
        r._content = b'{"$items": [{ "id": "abc123", "name": "Ari Fani", "email": "ari@test.com" }]}'
        return r


class TestSageService(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = UserFactory(
            accounting_org="sage", accounting_refresh_token="abc123"
        )

    def test_oauth(self):
        rf = RequestFactory()
        get_request = rf.get("/accounting-redirect?code=abc123&realmId=abc123")
        get_request.user = self.user

        with HTTMock(SageMocks.sage_oauth_mock):
            _ = SageService.get_auth_tokens(get_request)
            self.assertEqual(self.user.accounting_org_id, "abc123")

    def test_oauth_error(self):
        rf = RequestFactory()
        get_request = rf.get("/accounting-redirect?code=abc123&realmId=abc123")
        get_request.user = self.user

        with HTTMock(SageMocks.sage_oauth_error_mock):
            with self.assertRaises(AccountingError):
                _ = SageService.get_auth_tokens(get_request)

    def test_refresh_tokens(self):
        with HTTMock(SageMocks.sage_oauth_mock):
            refresh_token = SageService.get_refreshed_tokens(self.user)
            self.assertEqual(refresh_token, "abc123")

    def test_create_customer(self):
        self.user.accounting_org_id = "abc123"
        client = ClientFactory(user=self.user, accounting_customer_id="abc123")
        with HTTMock(SageMocks.sage_oauth_mock, SageMocks.sage_customer_mock):
            SageService.create_customer(client)
            client.refresh_from_db()
            self.assertEqual(client.accounting_customer_id, "abc123")

    def test_error_create_customer(self):
        self.user.accounting_org_id = "abc123"
        client = ClientFactory(user=self.user, accounting_customer_id="abc123")
        with HTTMock(SageMocks.sage_oauth_mock, SageMocks.sage_error_customer_mock):
            with self.assertRaises(AccountingError):
                SageService.create_customer(client)

    def test_create_invoice(self):
        self.user.accounting_org_id = "abc123"
        client = ClientFactory(user=self.user, accounting_customer_id="abc123")
        invoice = InvoiceFactory(user=self.user, client=client)
        sent_invoice = SentInvoiceFactory(invoice=invoice, user=self.user)
        with HTTMock(
            SageMocks.sage_oauth_mock,
            SageMocks.sage_invoice_ledger_mock,
            SageMocks.sage_invoice_bank_account_mock,
            SageMocks.sage_invoice_tax_rate_mock,
            SageMocks.sage_invoice_mock,
            SageMocks.sage_payment_mock,
        ):
            SageService.create_invoice(sent_invoice)
            sent_invoice.refresh_from_db()
            self.assertEqual(sent_invoice.accounting_invoice_id, "abc123")

    def test_error_create_invoice(self):
        self.user.sage_account_id = "abc123"
        client = ClientFactory(user=self.user, accounting_customer_id="abc123")
        invoice = InvoiceFactory(user=self.user, client=client)
        sent_invoice = SentInvoiceFactory(invoice=invoice, user=self.user)
        with HTTMock(
            SageMocks.sage_oauth_mock,
            SageMocks.sage_invoice_ledger_mock,
            SageMocks.sage_invoice_bank_account_mock,
            SageMocks.sage_invoice_tax_rate_mock,
            SageMocks.sage_error_invoice_mock,
            SageMocks.sage_error_payment_mock,
        ):
            with self.assertRaises(AccountingError):
                SageService.create_invoice(sent_invoice)

    def test_update_customer(self):
        self.user.accounting_org_id = "abc123"
        client = ClientFactory(user=self.user, accounting_customer_id="abc123")
        with HTTMock(SageMocks.sage_oauth_mock, SageMocks.sage_update_customer_mock):
            SageService.update_customer(client)
            client.refresh_from_db()
            self.assertEqual(client.accounting_customer_id, "abc123")

    def test_error_update_customer(self):
        self.user.accounting_org_id = "abc123"
        client = ClientFactory(user=self.user, accounting_customer_id="abc123")
        with HTTMock(
            SageMocks.sage_oauth_mock, SageMocks.sage_error_update_customer_mock
        ):
            with self.assertRaises(AccountingError):
                SageService.update_customer(client)

    def test_fetch_customers(self):
        self.user.accounting_org_id = "abc123"
        with HTTMock(SageMocks.sage_oauth_mock, SageMocks.sage_fetch_customers_mock):
            customers = SageService.get_customers(self.user)
            self.assertEqual(customers[0]["accounting_customer_id"], "abc123")
