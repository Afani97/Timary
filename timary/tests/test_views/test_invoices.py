import datetime
import json
import uuid
from unittest.mock import patch

from django.urls import reverse
from django.utils.http import urlencode

from timary.models import Invoice, SentInvoice
from timary.tests.factories import (
    DailyHoursFactory,
    InvoiceFactory,
    SentInvoiceFactory,
    UserFactory,
)
from timary.tests.test_views.basetest import BaseTest


class TestInvoices(BaseTest):
    def setUp(self) -> None:
        super().setUp()

        self.user = UserFactory()
        self.client.force_login(self.user)
        self.invoice = InvoiceFactory(user=self.user)
        self.invoice_no_user = InvoiceFactory()

    @classmethod
    def extract_html(cls, html):
        start = html.find("<main") + len("<main>")
        end = html.find("</main>")
        message = html[start:end]
        return message

    def test_create_invoice(self):
        Invoice.objects.all().delete()
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
        self.assertInHTML(
            f"""
            <h2 class="card-title">{invoice.title} - Rate: ${invoice.hourly_rate}</h2>
            <p>sent daily to {inv_name} ({inv_email})</p>
            <p>next date sent is: {invoice.next_date.strftime("%b. %-d, %Y")}</p>
            """,
            response.content.decode("utf-8"),
        )
        self.assertEqual(response.templates[0].name, "partials/_invoice.html")
        self.assertEqual(response.status_code, 200)

    def test_manage_invoices(self):
        response = self.client.get(reverse("timary:manage_invoices"))
        self.assertContains(
            response,
            f'<h2 class="card-title">{self.invoice.title} - Rate: ${self.invoice.hourly_rate}</h2>',
        )
        self.assertEqual(response.templates[0].name, "invoices/manage_invoices.html")
        self.assertEqual(response.status_code, 200)

    def test_manage_zero_invoices(self):
        Invoice.objects.filter(user=self.user).all().delete()
        response = self.client.get(reverse("timary:manage_invoices"))
        self.assertInHTML(
            """
            <div class="text-center lg:text-left md:mr-20">
                <h1 class="mb-5 text-5xl font-bold">
                    Hello there
                </h1>
                <p class="mb-5">
                    We all gotta start somewhere right? Begin your journey by adding your first invoicing details.
                </p>
            </div>
            """,
            response.content.decode("utf-8"),
        )
        self.assertEqual(response.templates[0].name, "invoices/manage_invoices.html")
        self.assertEqual(response.status_code, 200)

    def test_zero_invoices_redirects_main_page(self):
        Invoice.objects.filter(user=self.user).all().delete()
        response = self.client.get(reverse("timary:index"))
        self.assertRedirects(response, reverse("timary:manage_invoices"))
        self.assertEqual(response.status_code, 302)

    def test_create_invoice_error(self):
        response = self.client.post(reverse("timary:create_invoice"), {})
        self.assertEqual(response.status_code, 400)

    def test_get_invoice(self):
        rendered_template = self.setup_template(
            "partials/_invoice.html", {"invoice": self.invoice}
        )
        response = self.client.get(
            reverse("timary:get_single_invoice", kwargs={"invoice_id": self.invoice.id})
        )
        self.assertHTMLEqual(rendered_template, response.content.decode("utf-8"))

    def test_get_invoice_error(self):
        response = self.client.get(
            reverse(
                "timary:get_single_invoice",
                kwargs={"invoice_id": self.invoice_no_user.id},
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_delete_invoice(self):
        response = self.client.delete(
            reverse("timary:delete_invoice", kwargs={"invoice_id": self.invoice.id})
        )
        self.assertEqual(response.status_code, 200)

    def test_delete_daily_hours_error(self):
        response = self.client.delete(
            reverse(
                "timary:delete_invoice", kwargs={"invoice_id": self.invoice_no_user.id}
            ),
            data={},
        )
        self.assertEqual(response.status_code, 404)

    def test_edit_invoice(self):
        response = self.client.get(
            reverse("timary:edit_invoice", kwargs={"invoice_id": self.invoice.id}),
        )
        self.assertEqual(response.templates[0].name, "partials/_htmx_put_form.html")
        self.assertEqual(response.status_code, 200)

    def test_edit_invoice_error(self):
        response = self.client.get(
            reverse(
                "timary:edit_invoice", kwargs={"invoice_id": self.invoice_no_user.id}
            ),
            data={},
        )
        self.assertEqual(response.status_code, 404)

    def test_update_daily_hours(self):
        url_params = {
            "title": "Some title",
            "hourly_rate": 100,
            "invoice_interval": "D",
            "email_recipient_name": "Mike",
            "email_recipient": "mike@test.com",
        }
        response = self.client.put(
            reverse("timary:update_invoice", kwargs={"invoice_id": self.invoice.id}),
            data=urlencode(url_params),  # HTML PUT FORM
        )
        self.invoice.refresh_from_db()
        inv_name = self.invoice.email_recipient_name
        inv_email = self.invoice.email_recipient
        self.assertInHTML(
            f"""
            <h2 class="card-title">{self.invoice.title} - Rate: ${self.invoice.hourly_rate}</h2>
            <p>sent daily to {inv_name} ({inv_email})</p>
            <p>next date sent is: {self.invoice.next_date.strftime("%b. %-d, %Y")}</p>
            """,
            response.content.decode("utf-8"),
        )
        self.assertEqual(response.templates[0].name, "partials/_invoice.html")
        self.assertEqual(response.status_code, 200)

    def test_update_daily_hours_dont_update_next_date_if_none(self):
        url_params = {
            "title": "Some title",
            "hourly_rate": 100,
            "invoice_interval": "D",
            "email_recipient_name": "Mike",
            "email_recipient": "mike@test.com",
        }
        self.invoice.next_date = None
        self.invoice.save()
        response = self.client.put(
            reverse("timary:update_invoice", kwargs={"invoice_id": self.invoice.id}),
            data=urlencode(url_params),  # HTML PUT FORM
        )
        self.invoice.refresh_from_db()
        self.assertIsNone(self.invoice.next_date)
        self.assertInHTML(
            f"""
            <h2 class="card-title">{self.invoice.title} - Rate: ${self.invoice.hourly_rate}</h2>
            <p>invoice is paused</p>
            """,
            response.content.decode("utf-8"),
        )
        self.assertEqual(response.templates[0].name, "partials/_invoice.html")
        self.assertEqual(response.status_code, 200)

    def test_update_invoice_error(self):
        response = self.client.put(
            reverse(
                "timary:update_invoice", kwargs={"invoice_id": self.invoice_no_user.id}
            ),
            data={},
        )
        self.assertEqual(response.status_code, 404)

    def test_pause_invoice(self):
        invoice = InvoiceFactory(invoice_interval="M", user=self.user)
        response = self.client.get(
            reverse("timary:pause_invoice", kwargs={"invoice_id": invoice.id}),
        )
        invoice.refresh_from_db()
        self.assertIsNone(invoice.next_date)
        self.assertEqual(response.templates[0].name, "partials/_invoice.html")
        self.assertEqual(response.status_code, 200)

        response = self.client.get(
            reverse("timary:pause_invoice", kwargs={"invoice_id": invoice.id}),
        )
        invoice.refresh_from_db()

        self.assertEqual(
            invoice.next_date,
            datetime.date.today() + invoice.get_next_date(),
        )
        self.assertEqual(response.templates[0].name, "partials/_invoice.html")
        self.assertEqual(response.status_code, 200)

    def test_pause_invoice_error(self):
        response = self.client.get(
            reverse(
                "timary:pause_invoice", kwargs={"invoice_id": self.invoice_no_user.id}
            ),
            data={},
        )
        self.assertEqual(response.status_code, 404)

    def test_pay_invoice_already_paid(self):
        self.client.logout()

        sent_invoice = SentInvoiceFactory(paid_status=SentInvoice.PaidStatus.PAID)
        response = self.client.get(
            reverse("timary:pay_invoice", kwargs={"sent_invoice_id": sent_invoice.id}),
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("timary:login"))

    def test_raise_error_unknown_sent_invoice(self):
        self.client.logout()
        response = self.client.get(
            reverse("timary:pay_invoice", kwargs={"sent_invoice_id": uuid.uuid4()}),
        )
        self.assertEqual(response.status_code, 404)

    def test_sent_invoice_valid_details(self):
        self.client.logout()
        sent_invoice = SentInvoiceFactory()
        response = self.client.post(
            reverse("timary:pay_invoice", kwargs={"sent_invoice_id": sent_invoice.id}),
            data={
                "email": sent_invoice.invoice.email_recipient,
                "first_name": sent_invoice.invoice.email_recipient_name,
            },
        )
        self.assertEqual(response.status_code, 200)
        json_content = json.loads(response.content)
        self.assertEqual(json_content, {"valid": True, "errors": {}})

    def test_sent_invoice_invalid_details(self):
        self.client.logout()
        sent_invoice = SentInvoiceFactory()
        response = self.client.post(
            reverse("timary:pay_invoice", kwargs={"sent_invoice_id": sent_invoice.id}),
            data={
                "email": "user@test.com",
                "first_name": "User",
            },
        )
        self.assertEqual(response.status_code, 200)
        json_content = json.loads(response.content)
        expected_json = {
            "valid": False,
            "errors": '{"email": [{"message": "Wrong email recipient, unable to process payment", "code": ""}], '
            '"first_name": [{"message": "Wrong name recipient, unable to process payment", "code": ""}]}',
        }

        self.assertEqual(json_content, expected_json)

    @patch(
        "timary.services.stripe_service.StripeService.create_payment_intent_for_payout"
    )
    def test_get_pay_invoice(self, stripe_intent_mock):
        self.client.logout()
        stripe_intent_mock.return_value = "tok_abc123"

        sent_invoice = SentInvoiceFactory()
        today = datetime.date.today()
        for i in range(10):
            DailyHoursFactory(
                invoice=sent_invoice.invoice,
                date_tracked=today - datetime.timedelta(days=i),
            )
        sent_invoice.refresh_from_db()
        response = self.client.get(
            reverse("timary:pay_invoice", kwargs={"sent_invoice_id": sent_invoice.id}),
        )
        self.assertEqual(response.status_code, 200)

        html_body = self.extract_html(response.content.decode("utf-8"))

        with self.subTest("Testing summary"):
            msg = f"""
            <div class="mb-4">
                <h1 class="text-2xl mb-6">Hello! Thanks for using Timary</h1>
                <p class="mb-4">This is an invoice for {sent_invoice.invoice.user.first_name}'s services.</p>
                <p>Total Amount Due: ${sent_invoice.total_price}</p>
            </div>
            """
            self.assertInHTML(msg, html_body)

        with self.subTest("Testing total price in table"):
            msg = f"""
            <td width="20%" class="purchase_footer" valign="middle">
                <p class="f-fallback purchase_total">${sent_invoice.total_price}</p>
            </td>
            """
            self.assertInHTML(msg, html_body)

        with self.subTest("Testing payment info form renders"):
            msg = """
            <div class="form-control my-4 col-span-2">
                <label class="label"><span class="label-text">Your email</span></label>
                <input type="text" name="email" placeholder="john@appleseed.com" classes="col-span-2"
                class="input input-bordered bg-neutral focus:border-primary focus:ring-0 focus:ring-primary w-full"
                required id="id_email">
            </div>

            <div class="form-control my-4 col-span-2">
                <label class="label"><span class="label-text">Your first name</span></label>
                <input type="text" name="first_name" placeholder="John" classes="col-span-2"
                class="input input-bordered bg-neutral focus:border-primary focus:ring-0 focus:ring-primary w-full"
                required id="id_first_name">
            </div>
            """
            self.assertInHTML(msg, html_body)

        with self.subTest("Testing hours table renders all hours for invoice"):
            hours_tracked = sent_invoice.get_hours_tracked()
            msg = ""
            for i, hour in enumerate(hours_tracked, start=1):
                msg += f"""
                <tr>
                    <td>{i}</td>
                    <td width="80%" class="purchase_item"><span class="f-fallback">{ hour.hours } hours on
                    { hour.date_tracked.strftime("%b %-d") }</span></td>
                    <td class="align-right" width="20%" class="purchase_item">
                    <span class="f-fallback">${ int(hour.cost)}</span>
                    </td>
                </tr>
                """
            self.assertInHTML(msg, html_body)
