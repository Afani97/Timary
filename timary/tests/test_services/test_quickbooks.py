from django.test import Client, TestCase
from django.test.client import RequestFactory
from httmock import HTTMock, urlmatch
from requests import Response

from timary.custom_errors import AccountingError
from timary.services.quickbook_service import QuickbookService
from timary.tests.factories import InvoiceFactory, SentInvoiceFactory, UserFactory


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


class TestQuickbooksService(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = UserFactory()

    def test_oauth(self):
        rf = RequestFactory()
        get_request = rf.get("/quickbook-redirect?code=abc123&realmId=abc123")
        get_request.user = self.user

        with HTTMock(QuickbookMocks.quickbook_oauth_mock):
            auth_token = QuickbookService.get_auth_tokens(get_request)
            self.assertEquals(auth_token, "abc123")

    def test_oauth_token_error(self):
        rf = RequestFactory()
        get_request = rf.get("/quickbook-redirect?code=abc123&realmId=abc123")
        get_request.user = self.user

        with HTTMock(QuickbookMocks.quickbook_oauth_error_mock):
            with self.assertRaises(AccountingError):
                _ = QuickbookService.get_auth_tokens(get_request)

    def test_refresh_tokens(self):
        with HTTMock(QuickbookMocks.quickbook_oauth_mock):
            refresh_token = QuickbookService.get_refreshed_tokens(self.user)
            self.assertEquals(refresh_token, "abc123")

    def test_create_customer(self):
        self.user.quickbooks_realm_id = "abc123"
        invoice = InvoiceFactory(user=self.user)
        with HTTMock(
            QuickbookMocks.quickbook_oauth_mock, QuickbookMocks.quickbook_customer_mock
        ):
            QuickbookService.create_customer(invoice)
            invoice.refresh_from_db()
            self.assertEquals(invoice.quickbooks_customer_ref_id, "abc123")

    def test_error_create_customer(self):
        self.user.quickbooks_realm_id = "abc123"
        invoice = InvoiceFactory(user=self.user)
        with HTTMock(
            QuickbookMocks.quickbook_oauth_mock,
            QuickbookMocks.quickbook_error_customer_mock,
        ):
            with self.assertRaises(AccountingError):
                QuickbookService.create_customer(invoice)

    def test_create_invoice(self):
        self.user.quickbooks_realm_id = "abc123"
        invoice = InvoiceFactory(user=self.user, quickbooks_customer_ref_id="abc123")
        sent_invoice = SentInvoiceFactory(invoice=invoice, user=self.user)
        with HTTMock(
            QuickbookMocks.quickbook_oauth_mock,
            QuickbookMocks.quickbook_invoice_mock,
            QuickbookMocks.quickbook_payment_mock,
        ):
            QuickbookService.create_invoice(sent_invoice)
            sent_invoice.refresh_from_db()
            self.assertEquals(sent_invoice.quickbooks_invoice_id, "abc123")

    def test_error_create_invoice(self):
        self.user.quickbooks_realm_id = "abc123"
        invoice = InvoiceFactory(user=self.user, quickbooks_customer_ref_id="abc123")
        sent_invoice = SentInvoiceFactory(invoice=invoice, user=self.user)
        with HTTMock(
            QuickbookMocks.quickbook_oauth_mock,
            QuickbookMocks.quickbook_error_invoice_mock,
            QuickbookMocks.quickbook_payment_mock,
        ):
            with self.assertRaises(AccountingError):
                QuickbookService.create_invoice(sent_invoice)
