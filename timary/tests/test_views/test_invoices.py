import datetime
import uuid

from django.core import mail
from django.template.defaultfilters import date, floatformat
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

    def test_create_invoice(self):
        Invoice.objects.all().delete()
        response = self.client.post(
            reverse("timary:create_invoice"),
            {
                "title": "Some title",
                "hourly_rate": 50,
                "invoice_interval": "D",
                "email_recipient_name": "John Smith",
                "email_recipient": "john@test.com",
            },
        )

        invoice = Invoice.objects.first()
        inv_name = invoice.email_recipient_name
        inv_email = invoice.email_recipient
        self.assertInHTML(
            f"""
            <h2 class="card-title">{invoice.title} - Rate: ${invoice.hourly_rate}</h2>
            <p class="text-xl">sent daily to {inv_name} ({inv_email})</p>
            <p class="text-xl">next date sent is: {invoice.next_date.strftime("%B %-d, %Y")}</p>
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
                <h1 class="mb-5 text-5xl font-bold" id="intro-text">
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

    def test_get_invoice_with_hours_logged(self):
        hour = DailyHoursFactory(invoice=self.invoice)

        rendered_template = self.setup_template(
            "partials/_invoice.html", {"invoice": self.invoice}
        )
        response = self.client.get(
            reverse("timary:get_single_invoice", kwargs={"invoice_id": self.invoice.id})
        )
        self.assertHTMLEqual(rendered_template, response.content.decode("utf-8"))
        self.assertInHTML(
            f"""
           <div tabindex="0" class="collapse collapse-arrow rounded-md -mx-3">
             <div class="collapse-title text-xl font-medium">View hours logged this period</div>
             <div class="collapse-content" id="hours-logged">
               <ul class="list-disc mx-5">

                     <li class="text-xl">{floatformat(hour.hours)} hrs on {date(hour.date_tracked, "M jS")}</li>

               </ul>
             </div>
           </div>
           """,
            response.content.decode("utf-8"),
        )

    def test_get_invoice_error(self):
        response = self.client.get(
            reverse(
                "timary:get_single_invoice",
                kwargs={"invoice_id": self.invoice_no_user.id},
            )
        )
        self.assertEqual(response.status_code, 302)

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
        self.assertEqual(response.status_code, 302)

    def test_edit_invoice(self):
        response = self.client.get(
            reverse("timary:edit_invoice", kwargs={"invoice_id": self.invoice.id}),
        )
        self.assertEqual(response.status_code, 200)

    def test_edit_invoice_error(self):
        response = self.client.get(
            reverse(
                "timary:edit_invoice", kwargs={"invoice_id": self.invoice_no_user.id}
            ),
            data={},
        )
        self.assertEqual(response.status_code, 302)

    def test_update_daily_hours(self):
        url_params = {
            "title": "Some title",
            "hourly_rate": 100,
            "invoice_interval": "D",
            "email_recipient_name": "John Smith",
            "email_recipient": "john@test.com",
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
            <p class="text-xl">sent daily to {inv_name} ({inv_email})</p>
            <p class="text-xl">next date sent is: {self.invoice.next_date.strftime("%B %-d, %Y")}</p>
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
            "email_recipient_name": "John Smith",
            "email_recipient": "john@test.com",
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
            <p class="text-xl">invoice is paused</p>
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
        self.assertEqual(response.status_code, 302)

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
        self.assertEqual(response.status_code, 302)

    def test_resend_invoice_email(self):
        invoice = InvoiceFactory(user=self.user)
        sent_invoice = SentInvoiceFactory(invoice=invoice)

        response = self.client.get(
            reverse(
                "timary:resend_invoice_email",
                kwargs={"sent_invoice_id": sent_invoice.id},
            ),
        )
        self.assertEqual(len(mail.outbox), 1)
        expected_context = {"sent_invoice": sent_invoice, "invoice_resent": True}
        expected_response = self.setup_template(
            "partials/_sent_invoice.html", expected_context
        )
        self.assertEqual(expected_response, response.content.decode("utf-8"))

    def test_resend_invoice_email_already_paid(self):
        invoice = InvoiceFactory(user=self.user)
        sent_invoice = SentInvoiceFactory(
            invoice=invoice, paid_status=SentInvoice.PaidStatus.PAID
        )

        response = self.client.get(
            reverse(
                "timary:resend_invoice_email",
                kwargs={"sent_invoice_id": sent_invoice.id},
            ),
        )
        self.assertRedirects(response, reverse("timary:user_profile"))

    def test_resend_invoice_email_error(self):
        response = self.client.get(
            reverse(
                "timary:resend_invoice_email",
                kwargs={"sent_invoice_id": uuid.uuid4()},
            ),
        )
        self.assertEqual(response.status_code, 302)
