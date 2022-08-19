from django.test import Client, TestCase
from django.test.client import RequestFactory
from httmock import HTTMock, urlmatch
from requests import Response

from timary.custom_errors import AccountingError
from timary.services.xero_service import XeroService
from timary.tests.factories import InvoiceFactory, SentInvoiceFactory, UserFactory


class XeroMocks:
    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="identity.xero.com",
        path="/connect/token",
        method="POST",
    )
    def xero_oauth_mock(url, request):
        r = Response()
        r.status_code = 200
        r._content = b'{"refresh_token": "abc123", "access_token": "abc123"}'
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="identity.xero.com",
        path="/connect/token",
        method="POST",
    )
    def xero_oauth_error_mock(url, request):
        r = Response()
        r.status_code = 200
        r._content = b"{}"
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="api.xero.com",
        path="/connections",
        method="GET",
    )
    def xero_oauth_tenant_mock(url, request):
        r = Response()
        r.status_code = 200
        r._content = b'[{"tenantId": "abc123"}]'
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="api.xero.com",
        path="/api.xro/2.0/Contacts",
        method="POST",
    )
    def xero_customer_mock(url, request):
        r = Response()
        r.status_code = 200
        r._content = b'{"Contacts": [{ "ContactID": "abc123"}] }'
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="api.xero.com",
        path="/api.xro/2.0/Contacts",
        method="POST",
    )
    def xero_error_customer_mock(url, request):
        r = Response()
        r.status_code = 400
        r._content = b"{}"
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="api.xero.com",
        path="/api.xro/2.0/Invoices",
        method="POST",
    )
    def xero_invoice_mock(url, request):
        r = Response()
        r.status_code = 200
        r._content = b'{"Invoices": [{"InvoiceID": "abc123"}]}'
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="api.xero.com",
        path="/api.xro/2.0/Invoices",
        method="POST",
    )
    def xero_error_invoice_mock(url, request):
        r = Response()
        r.status_code = 400
        r._content = b"{}"
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="api.xero.com",
        path="/api.xro/2.0/Payments",
        method="PUT",
    )
    def xero_payment_mock(url, request):
        r = Response()
        r.status_code = 200
        r._content = b'{"Invoices": [{"InvoiceID": "abc123"}]}'
        return r


class TestXeroService(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = UserFactory(
            accounting_org="xero", accounting_refresh_token="abc123"
        )

    def test_oauth(self):
        rf = RequestFactory()
        get_request = rf.get("/accounting-redirect-redirect?code=abc123&realmId=abc123")
        get_request.user = self.user

        with HTTMock(XeroMocks.xero_oauth_mock, XeroMocks.xero_oauth_tenant_mock):
            _ = XeroService.get_auth_tokens(get_request)
            self.assertEquals(self.user.accounting_org_id, "abc123")

    def test_oauth_error(self):
        rf = RequestFactory()
        get_request = rf.get("/accounting-redirect?code=abc123&realmId=abc123")
        get_request.user = self.user

        with HTTMock(XeroMocks.xero_oauth_error_mock, XeroMocks.xero_oauth_tenant_mock):
            with self.assertRaises(AccountingError):
                _ = XeroService.get_auth_tokens(get_request)

    def test_refresh_tokens(self):
        with HTTMock(XeroMocks.xero_oauth_mock):
            refresh_token = XeroService.get_refreshed_tokens(self.user)
            self.assertEquals(refresh_token, "abc123")

    def test_create_customer(self):
        self.user.accounting_org_id = "abc123"
        invoice = InvoiceFactory(user=self.user)
        with HTTMock(XeroMocks.xero_oauth_mock, XeroMocks.xero_customer_mock):
            XeroService.create_customer(invoice)
            invoice.refresh_from_db()
            self.assertEquals(invoice.accounting_customer_id, "abc123")

    def test_error_create_customer(self):
        self.user.accounting_org_id = "abc123"
        invoice = InvoiceFactory(user=self.user)
        with HTTMock(XeroMocks.xero_oauth_mock, XeroMocks.xero_error_customer_mock):
            with self.assertRaises(AccountingError):
                XeroService.create_customer(invoice)

    def test_create_invoice(self):
        self.user.accounting_org_id = "abc123"
        invoice = InvoiceFactory(user=self.user, accounting_customer_id="abc123")
        sent_invoice = SentInvoiceFactory(invoice=invoice, user=self.user)
        with HTTMock(
            XeroMocks.xero_oauth_mock,
            XeroMocks.xero_invoice_mock,
            XeroMocks.xero_payment_mock,
        ):
            XeroService.create_invoice(sent_invoice)
            sent_invoice.refresh_from_db()
            self.assertEquals(sent_invoice.accounting_invoice_id, "abc123")

    def test_error_create_invoice(self):
        self.user.accounting_org_id = "abc123"
        invoice = InvoiceFactory(user=self.user, accounting_customer_id="abc123")
        sent_invoice = SentInvoiceFactory(invoice=invoice, user=self.user)
        with HTTMock(
            XeroMocks.xero_oauth_mock,
            XeroMocks.xero_error_invoice_mock,
            XeroMocks.xero_payment_mock,
        ):
            with self.assertRaises(AccountingError):
                XeroService.create_invoice(sent_invoice)
