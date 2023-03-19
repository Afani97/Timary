from django.test import Client, TestCase
from django.test.client import RequestFactory
from httmock import HTTMock, urlmatch
from requests import Response

from timary.custom_errors import AccountingError
from timary.services.freshbooks_service import FreshbooksService
from timary.tests.factories import (
    ClientFactory,
    InvoiceFactory,
    SentInvoiceFactory,
    UserFactory,
)


class FreshbookMocks:
    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="api.freshbooks.com",
        path="/auth/oauth/token",
        method="POST",
    )
    def freshbook_oauth_mock(url, request):
        r = Response()
        r.status_code = 200
        r._content = b'{"refresh_token": "abc123", "access_token": "abc123"}'
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="api.freshbooks.com",
        path="/auth/oauth/token",
        method="POST",
    )
    def freshbook_oauth_error_mock(url, request):
        r = Response()
        r.status_code = 200
        r._content = b"{}"
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="api.freshbooks.com",
        path="/auth/api/v1/users/me",
        method="GET",
    )
    def freshbook_org_mock(url, request):
        r = Response()
        r.status_code = 200
        r._content = b'{"response": {"business_memberships": [{"business": {"account_id": "abc123"}}]}}'
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="api.freshbooks.com",
        path="/accounting/account/abc123/users/clients",
        method="POST",
    )
    def freshbook_customer_mock(url, request):
        r = Response()
        r.status_code = 200
        r._content = b'{"response": {"result": {"client": {"id": "abc123"}}}}'
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="api.freshbooks.com",
        path="/accounting/account/abc123/users/clients/abc123",
        method="POST",
    )
    def freshbook_update_customer_mock(url, request):
        r = Response()
        r.status_code = 200
        r._content = b'{"response": {"result": {"client": {"id": "abc123"}}}}'
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="api.freshbooks.com",
        path="/accounting/account/abc123/users/clients",
        method="POST",
    )
    def freshbook_error_customer_mock(url, request):
        r = Response()
        r.status_code = 400
        r._content = b"{}"
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="api.freshbooks.com",
        path="/accounting/account/abc123/users/clients/abc123",
        method="POST",
    )
    def freshbook_error_update_customer_mock(url, request):
        r = Response()
        r.status_code = 400
        r._content = b"{}"
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="api.freshbooks.com",
        path="/accounting/account/abc123/invoices/invoices",
        method="POST",
    )
    def freshbook_invoice_mock(url, request):
        r = Response()
        r.status_code = 200
        r._content = b'{"response": {"result": {"invoice": {"id": "abc123"}}}}'
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="api.freshbooks.com",
        path="/accounting/account/abc123/invoices/invoices",
        method="POST",
    )
    def freshbook_error_invoice_mock(url, request):
        r = Response()
        r.status_code = 400
        r._content = b"{}"
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="api.freshbooks.com",
        path="/accounting/account/abc123/payments/payments",
        method="POST",
    )
    def freshbook_payment_mock(url, request):
        r = Response()
        r.status_code = 200
        r._content = b'{"response": {"result": {"invoice": {"id": "abc123"}}}}'
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="api.freshbooks.com",
        path="/accounting/account/abc123/users/client",
        method="GET",
    )
    def freshbook_fetch_customers_mock(url, request):
        r = Response()
        r.status_code = 200
        r._content = b'{"response": {"result": {"clients": [{"id": "abc123", "fname": "Ari", "lname": "Fani"}]}}}'
        return r


class TestFreshbooksService(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = UserFactory(
            accounting_org="freshbooks", accounting_refresh_token="abc123"
        )

    def test_oauth(self):
        rf = RequestFactory()
        get_request = rf.get("/accounting-redirect?code=abc123&realmId=abc123")
        get_request.user = self.user

        with HTTMock(
            FreshbookMocks.freshbook_oauth_mock, FreshbookMocks.freshbook_org_mock
        ):
            auth_token = FreshbooksService.get_auth_tokens(get_request)
            self.assertEquals(auth_token, "abc123")

    def test_oauth_error(self):
        rf = RequestFactory()
        get_request = rf.get("/accounting-redirect?code=abc123&realmId=abc123")
        get_request.user = self.user

        with HTTMock(FreshbookMocks.freshbook_oauth_error_mock):
            with self.assertRaises(AccountingError):
                _ = FreshbooksService.get_auth_tokens(get_request)

    def test_refresh_tokens(self):
        with HTTMock(FreshbookMocks.freshbook_oauth_mock):
            refresh_token = FreshbooksService.get_refreshed_tokens(self.user)
            self.assertEquals(refresh_token, "abc123")

    def test_create_customer(self):
        self.user.accounting_org_id = "abc123"
        client = ClientFactory(user=self.user)
        with HTTMock(
            FreshbookMocks.freshbook_oauth_mock, FreshbookMocks.freshbook_customer_mock
        ):
            FreshbooksService.create_customer(client)
            client.refresh_from_db()
            self.assertEquals(client.accounting_customer_id, "abc123")

    def test_error_create_customer(self):
        self.user.accounting_org_id = "abc123"
        client = ClientFactory(user=self.user)
        with HTTMock(
            FreshbookMocks.freshbook_oauth_mock,
            FreshbookMocks.freshbook_error_customer_mock,
        ):
            with self.assertRaises(AccountingError):
                FreshbooksService.create_customer(client)

    def test_create_invoice(self):
        self.user.accounting_org_id = "abc123"
        client = ClientFactory(user=self.user, accounting_customer_id="abc123")
        invoice = InvoiceFactory(user=self.user, client=client)
        sent_invoice = SentInvoiceFactory(invoice=invoice, user=self.user)
        with HTTMock(
            FreshbookMocks.freshbook_oauth_mock,
            FreshbookMocks.freshbook_invoice_mock,
            FreshbookMocks.freshbook_payment_mock,
        ):
            FreshbooksService.create_invoice(sent_invoice)
            sent_invoice.refresh_from_db()
            self.assertEquals(sent_invoice.accounting_invoice_id, "abc123")

    def test_error_create_invoice(self):
        self.user.accounting_org_id = "abc123"
        client = ClientFactory(user=self.user, accounting_customer_id="abc123")
        invoice = InvoiceFactory(user=self.user, client=client)
        sent_invoice = SentInvoiceFactory(invoice=invoice, user=self.user)
        with HTTMock(
            FreshbookMocks.freshbook_oauth_mock,
            FreshbookMocks.freshbook_error_invoice_mock,
            FreshbookMocks.freshbook_payment_mock,
        ):
            with self.assertRaises(AccountingError):
                FreshbooksService.create_invoice(sent_invoice)

    def test_update_customer(self):
        self.user.accounting_org_id = "abc123"
        client = ClientFactory(user=self.user, accounting_customer_id="abc123")
        with HTTMock(
            FreshbookMocks.freshbook_oauth_mock,
            FreshbookMocks.freshbook_update_customer_mock,
        ):
            FreshbooksService.update_customer(client)
            client.refresh_from_db()
            self.assertEquals(client.accounting_customer_id, "abc123")

    def test_error_update_customer(self):
        self.user.accounting_org_id = "abc123"
        client = ClientFactory(user=self.user, accounting_customer_id="abc123")
        with HTTMock(
            FreshbookMocks.freshbook_oauth_mock,
            FreshbookMocks.freshbook_error_update_customer_mock,
        ):
            with self.assertRaises(AccountingError):
                FreshbooksService.update_customer(client)

    def test_fetch_customers(self):
        self.user.accounting_org_id = "abc123"
        with HTTMock(
            FreshbookMocks.freshbook_oauth_mock,
            FreshbookMocks.freshbook_fetch_customers_mock,
        ):
            customers = FreshbooksService.get_customers(self.user)
            self.assertEquals(customers[0]["accounting_customer_id"], "abc123")
