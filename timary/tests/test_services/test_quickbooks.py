from django.test import Client, TestCase
from django.test.client import RequestFactory
from httmock import HTTMock, urlmatch
from requests import Response

from timary.custom_errors import AccountingError
from timary.services.quickbooks_service import QuickbooksService
from timary.tests.factories import (
    ClientFactory,
    InvoiceFactory,
    SentInvoiceFactory,
    UserFactory,
)


class QuickbookMocks:
    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="oauth.platform.intuit.com",
        path="/oauth2/v1/tokens/bearer",
        method="POST",
    )
    def quickbook_oauth_mock(url, request):
        r = Response()
        r.status_code = 200
        r._content = b'{"refresh_token": "abc123", "access_token": "abc123"}'
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="oauth.platform.intuit.com",
        path="/oauth2/v1/tokens/bearer",
        method="POST",
    )
    def quickbook_oauth_error_mock(url, request):
        r = Response()
        r.status_code = 200
        r._content = b"{}"
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="sandbox-quickbooks.api.intuit.com",
        path="/v3/company/abc123/customer",
        method="POST",
    )
    def quickbook_customer_mock(url, request):
        r = Response()
        r.status_code = 200
        r._content = b'{"Customer": {"Id": "abc123"}}'
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="sandbox-quickbooks.api.intuit.com",
        path="/v3/company/abc123/customer",
        method="POST",
    )
    def quickbook_error_customer_mock(url, request):
        r = Response()
        r.status_code = 400
        r._content = b"{}"
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="sandbox-quickbooks.api.intuit.com",
        path="/v3/company/abc123/customer",
        method="POST",
    )
    def quickbook_update_customer_mock(url, request):
        r = Response()
        r.status_code = 200
        r._content = b'{"Customer": {"Id": "abc123"}}'
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="sandbox-quickbooks.api.intuit.com",
        path="/v3/company/abc123/customer",
        method="POST",
    )
    def quickbook_error_update_customer_mock(url, request):
        r = Response()
        r.status_code = 400
        r._content = b"{}"
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="sandbox-quickbooks.api.intuit.com",
        path="/v3/company/abc123/invoice",
        method="POST",
    )
    def quickbook_invoice_mock(url, request):
        r = Response()
        r.status_code = 200
        r._content = b'{"Invoice": {"Id": "abc123"}}'
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="sandbox-quickbooks.api.intuit.com",
        path="/v3/company/abc123/invoice",
        method="POST",
    )
    def quickbook_error_invoice_mock(url, request):
        r = Response()
        r.status_code = 400
        r._content = b"{}"
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="sandbox-quickbooks.api.intuit.com",
        path="/v3/company/abc123/payment",
        method="POST",
    )
    def quickbook_payment_mock(url, request):
        r = Response()
        r.status_code = 200
        r._content = b'{"Invoice": {"Id": "abc123"}}'
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="sandbox-quickbooks.api.intuit.com",
        path="/v3/company/abc123/query",
        method="GET",
    )
    def quickbooks_fetch_customers_mock(url, request):
        r = Response()
        r.status_code = 200
        r._content = b'{"QueryResponse": {"Customer": [{"Id": "abc123", "DisplayName": "Ari Fani"}]}}'
        return r


class TestQuickbooksService(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = UserFactory(
            accounting_org="quickbooks", accounting_refresh_token="abc123"
        )

    def test_oauth(self):
        rf = RequestFactory()
        get_request = rf.get("/accounting-redirect?code=abc123&realmId=abc123")
        get_request.user = self.user

        with HTTMock(QuickbookMocks.quickbook_oauth_mock):
            auth_token = QuickbooksService.get_auth_tokens(get_request)
            self.assertEqual(auth_token, "abc123")

    def test_oauth_token_error(self):
        rf = RequestFactory()
        get_request = rf.get("/accounting-redirect?code=abc123&realmId=abc123")
        get_request.user = self.user

        with HTTMock(QuickbookMocks.quickbook_oauth_error_mock):
            with self.assertRaises(AccountingError):
                _ = QuickbooksService.get_auth_tokens(get_request)

    def test_refresh_tokens(self):
        with HTTMock(QuickbookMocks.quickbook_oauth_mock):
            refresh_token = QuickbooksService.get_refreshed_tokens(self.user)
            self.assertEqual(refresh_token, "abc123")

    def test_create_customer(self):
        self.user.accounting_org_id = "abc123"
        client = ClientFactory(user=self.user)
        with HTTMock(
            QuickbookMocks.quickbook_oauth_mock, QuickbookMocks.quickbook_customer_mock
        ):
            QuickbooksService.create_customer(client)
            client.refresh_from_db()
            self.assertEqual(client.accounting_customer_id, "abc123")

    def test_error_create_customer(self):
        self.user.accounting_org_id = "abc123"
        client = ClientFactory(user=self.user)
        with HTTMock(
            QuickbookMocks.quickbook_oauth_mock,
            QuickbookMocks.quickbook_error_customer_mock,
        ):
            with self.assertRaises(AccountingError):
                QuickbooksService.create_customer(client)

    def test_create_invoice(self):
        self.user.accounting_org_id = "abc123"
        client = ClientFactory(user=self.user, accounting_customer_id="abc123")
        invoice = InvoiceFactory(
            user=self.user,
            client=client,
        )
        sent_invoice = SentInvoiceFactory(invoice=invoice, user=self.user)
        with HTTMock(
            QuickbookMocks.quickbook_oauth_mock,
            QuickbookMocks.quickbook_invoice_mock,
            QuickbookMocks.quickbook_payment_mock,
        ):
            QuickbooksService.create_invoice(sent_invoice)
            sent_invoice.refresh_from_db()
            self.assertEqual(sent_invoice.accounting_invoice_id, "abc123")

    def test_error_create_invoice(self):
        self.user.accounting_org_id = "abc123"
        client = ClientFactory(user=self.user, accounting_customer_id="abc123")
        invoice = InvoiceFactory(
            user=self.user,
            client=client,
        )
        sent_invoice = SentInvoiceFactory(invoice=invoice, user=self.user)
        with HTTMock(
            QuickbookMocks.quickbook_oauth_mock,
            QuickbookMocks.quickbook_error_invoice_mock,
            QuickbookMocks.quickbook_payment_mock,
        ):
            with self.assertRaises(AccountingError):
                QuickbooksService.create_invoice(sent_invoice)

    def test_update_customer(self):
        self.user.accounting_org_id = "abc123"
        client = ClientFactory(user=self.user)
        with HTTMock(
            QuickbookMocks.quickbook_oauth_mock,
            QuickbookMocks.quickbook_update_customer_mock,
        ):
            QuickbooksService.update_customer(client)
            client.refresh_from_db()
            self.assertEqual(client.accounting_customer_id, "abc123")

    def test_error_update_customer(self):
        self.user.accounting_org_id = "abc123"
        client = ClientFactory(user=self.user)
        with HTTMock(
            QuickbookMocks.quickbook_oauth_mock,
            QuickbookMocks.quickbook_error_update_customer_mock,
        ):
            with self.assertRaises(AccountingError):
                QuickbooksService.update_customer(client)

    def test_fetch_customers(self):
        self.user.accounting_org_id = "abc123"
        with HTTMock(
            QuickbookMocks.quickbook_oauth_mock,
            QuickbookMocks.quickbooks_fetch_customers_mock,
        ):
            customers = QuickbooksService.get_customers(self.user)
            self.assertEqual(customers[0]["accounting_customer_id"], "abc123")
