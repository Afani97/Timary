from django.test import Client, TestCase
from django.test.client import RequestFactory
from httmock import HTTMock, urlmatch
from requests import Response

from timary.custom_errors import AccountingError
from timary.services.zoho_service import ZohoService
from timary.tests.factories import InvoiceFactory, SentInvoiceFactory, UserFactory


class ZohoMocks:
    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="accounts.zoho.com",
        path="/oauth/v2/token",
        method="POST",
    )
    def zoho_oauth_mock(url, request):
        r = Response()
        r.status_code = 200
        r._content = b'{"refresh_token": "abc123", "access_token": "abc123"}'
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="accounts.zoho.com",
        path="/oauth/v2/token",
        method="POST",
    )
    def zoho_oauth_error_mock(url, request):
        r = Response()
        r.status_code = 200
        r._content = b"{}"
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="invoice.zoho.com",
        path="/api/v3/contacts",
        method="POST",
    )
    def zoho_customer_mock(url, request):
        r = Response()
        r.status_code = 200
        r._content = b'{"contact": { "contact_id": "abc123", "contact_persons": [{"contact_person_id": "abc123"}] }}'
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="invoice.zoho.com",
        path="/api/v3/contacts",
        method="POST",
    )
    def zoho_error_customer_mock(url, request):
        r = Response()
        r.status_code = 400
        r._content = b'{"contact": { }}'
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="invoice.zoho.com",
        path="/api/v3/items",
        method="POST",
    )
    def zoho_invoice_items_mock(url, request):
        r = Response()
        r.status_code = 200
        r._content = b'{"item": {"item_id": "abc123"}}'
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="invoice.zoho.com",
        path="/api/v3/items/abc123/active",
        method="POST",
    )
    def zoho_invoice_items_active_mock(url, request):
        r = Response()
        r.status_code = 200
        r._content = b'{"item": {"item_id": "abc123"}}'
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="invoice.zoho.com",
        path="/api/v3/invoices",
        method="POST",
    )
    def zoho_invoice_mock(url, request):
        r = Response()
        r.status_code = 200
        r._content = b'{"invoice": {"invoice_id": "abc123"}}'
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="invoice.zoho.com",
        path="/api/v3/invoices",
        method="POST",
    )
    def zoho_error_invoice_mock(url, request):
        r = Response()
        r.status_code = 400
        r._content = b"{}"
        return r

    @staticmethod
    @urlmatch(
        scheme="https",
        netloc="invoice.zoho.com",
        path="/api/v3/customerpayments",
        method="POST",
    )
    def zoho_payment_mock(url, request):
        r = Response()
        r.status_code = 200
        r._content = b'{"invoice": {"invoice_id": "abc123"}}'
        return r


class TestZohoService(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = UserFactory()

    def test_oauth(self):
        rf = RequestFactory()
        get_request = rf.get("/zoho-redirect?code=abc123&realmId=abc123")
        get_request.user = self.user

        with HTTMock(ZohoMocks.zoho_oauth_mock):
            auth_token = ZohoService.get_auth_tokens(get_request)
            self.assertEquals(auth_token, "abc123")

    def test_oauth_error(self):
        rf = RequestFactory()
        get_request = rf.get("/zoho-redirect?code=abc123&realmId=abc123")
        get_request.user = self.user

        with HTTMock(ZohoMocks.zoho_oauth_error_mock):
            with self.assertRaises(AccountingError):
                _ = ZohoService.get_auth_tokens(get_request)

    def test_refresh_tokens(self):
        with HTTMock(ZohoMocks.zoho_oauth_mock):
            refresh_token = ZohoService.get_refreshed_tokens(self.user)
            self.assertEquals(refresh_token, "abc123")

    def test_create_customer(self):
        self.user.zoho_organization_id = "abc123"
        invoice = InvoiceFactory(user=self.user)
        with HTTMock(ZohoMocks.zoho_oauth_mock, ZohoMocks.zoho_customer_mock):
            ZohoService.create_customer(invoice)
            invoice.refresh_from_db()
            self.assertEquals(invoice.zoho_contact_id, "abc123")

    def test_error_create_customer(self):
        self.user.zoho_organization_id = "abc123"
        invoice = InvoiceFactory(user=self.user)
        with HTTMock(ZohoMocks.zoho_oauth_mock, ZohoMocks.zoho_error_customer_mock):
            with self.assertRaises(AccountingError):
                ZohoService.create_customer(invoice)

    def test_create_invoice(self):
        self.user.zoho_organization_id = "abc123"
        invoice = InvoiceFactory(user=self.user, zoho_contact_id="abc123")
        sent_invoice = SentInvoiceFactory(invoice=invoice, user=self.user)
        with HTTMock(
            ZohoMocks.zoho_oauth_mock,
            ZohoMocks.zoho_invoice_items_mock,
            ZohoMocks.zoho_invoice_items_active_mock,
            ZohoMocks.zoho_invoice_mock,
            ZohoMocks.zoho_payment_mock,
        ):
            ZohoService.create_invoice(sent_invoice)
            sent_invoice.refresh_from_db()
            self.assertEquals(sent_invoice.zoho_invoice_id, "abc123")

    def test_error_create_invoice(self):
        self.user.zoho_organization_id = "abc123"
        invoice = InvoiceFactory(user=self.user, zoho_contact_id="abc123")
        sent_invoice = SentInvoiceFactory(invoice=invoice, user=self.user)
        with HTTMock(
            ZohoMocks.zoho_oauth_mock,
            ZohoMocks.zoho_invoice_items_mock,
            ZohoMocks.zoho_invoice_items_active_mock,
            ZohoMocks.zoho_error_invoice_mock,
            ZohoMocks.zoho_payment_mock,
        ):
            with self.assertRaises(AccountingError):
                ZohoService.create_invoice(sent_invoice)
