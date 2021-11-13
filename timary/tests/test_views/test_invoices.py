import uuid

from django.urls import reverse
from django.utils.http import urlencode

from timary.models import Invoice
from timary.tests.factories import InvoiceFactory, UserProfilesFactory
from timary.tests.test_views.basetest import BaseTest


class TestInvoices(BaseTest):
    def setUp(self) -> None:
        super().setUp()

        self.user = UserProfilesFactory()
        self.client.force_login(self.user.user)

    def test_create_invoice(self):
        response = self.client.post(
            reverse("timary:create_invoice"),
            {
                "title": "Some title",
                "hourly_rate": 50,
                "invoice_interval": "D",
                "email_recipient_name": "Mike",
                "email_recipient": "mike@test.com",
            },
        )

        invoice = Invoice.objects.first()
        inv_name = invoice.email_recipient_name
        inv_email = invoice.email_recipient
        self.assertContains(
            response,
            f"""
        <div>
            <p class="text-xl">{invoice.title} - Rate: ${invoice.hourly_rate}</p>
            <div class="text-sm">Invoice is sent daily to {inv_name} ({inv_email})</div>
            <div class="text-sm">Next date sent is: {invoice.next_date.strftime("%b. %d, %Y")}</div>
        </div>""",
        )
        self.assertEqual(response.templates[0].name, "partials/_invoice.html")
        self.assertEqual(response.status_code, 200)

    def test_manage_invoices(self):
        invoice = InvoiceFactory(user=self.user)
        response = self.client.get(reverse("timary:manage_invoices"))
        # invoice.refresh_from_db()
        # print(response.content.decode())
        self.assertContains(
            response,
            f'<p class="text-xl">{invoice.title} - Rate: ${invoice.hourly_rate}</p>',
        )
        self.assertEqual(response.templates[0].name, "invoices/manage_invoices.html")
        self.assertEqual(response.status_code, 200)

    def test_create_invoice_error(self):
        response = self.client.post(reverse("timary:create_invoice"), {})
        self.assertEqual(response.status_code, 404)

    def test_get_invoice(self):
        invoice = InvoiceFactory()
        rendered_template = self.setup_template(
            "partials/_invoice.html", {"invoice": invoice}
        )
        response = self.client.get(
            reverse("timary:get_single_invoice", kwargs={"invoice_id": invoice.id})
        )
        self.assertHTMLEqual(rendered_template, response.content.decode("utf-8"))

    def test_get_invoice_error(self):
        response = self.client.get(
            reverse("timary:get_single_invoice", kwargs={"invoice_id": uuid.uuid4()})
        )
        self.assertEqual(response.status_code, 404)

    def test_delete_invoice(self):
        invoice = InvoiceFactory()
        response = self.client.delete(
            reverse("timary:delete_invoice", kwargs={"invoice_id": invoice.id})
        )
        self.assertEqual(response.status_code, 204)

    def test_delete_daily_hours_error(self):
        response = self.client.delete(
            reverse("timary:delete_invoice", kwargs={"invoice_id": uuid.uuid4()}),
            data={},
        )
        self.assertEqual(response.status_code, 404)

    def test_edit_invoice(self):
        invoice = InvoiceFactory()
        response = self.client.get(
            reverse("timary:edit_invoice", kwargs={"invoice_id": invoice.id}),
        )
        self.assertEqual(response.templates[0].name, "invoices/edit_invoice.html")
        self.assertEqual(response.status_code, 200)

    def test_edit_invoice_error(self):
        response = self.client.get(
            reverse("timary:edit_invoice", kwargs={"invoice_id": uuid.uuid4()}),
            data={},
        )
        self.assertEqual(response.status_code, 404)

    def test_update_daily_hours(self):
        invoice = InvoiceFactory()
        url_params = {
            "title": "Some title",
            "hourly_rate": 100,
            "invoice_interval": "D",
            "email_recipient_name": "Mike",
            "email_recipient": "mike@test.com",
        }
        response = self.client.put(
            reverse("timary:update_invoice", kwargs={"invoice_id": invoice.id}),
            data=urlencode(url_params),  # HTML PUT FORM
        )
        invoice.refresh_from_db()
        inv_name = invoice.email_recipient_name
        inv_email = invoice.email_recipient
        self.assertContains(
            response,
            f"""
        <div>
            <p class="text-xl">{invoice.title} - Rate: ${invoice.hourly_rate}</p>
            <div class="text-sm">Invoice is sent daily to {inv_name} ({inv_email})</div>
            <div class="text-sm">Next date sent is: {invoice.next_date.strftime("%b. %d, %Y")}</div>
        </div>""",
        )
        self.assertEqual(response.templates[0].name, "partials/_invoice.html")
        self.assertEqual(response.status_code, 200)

    def test_update_invoice_error(self):
        response = self.client.put(
            reverse("timary:update_invoice", kwargs={"invoice_id": uuid.uuid4()}),
            data={},
        )
        self.assertEqual(response.status_code, 404)
