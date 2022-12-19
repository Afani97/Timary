import datetime
import uuid
from unittest.mock import patch

from dateutil.relativedelta import relativedelta
from django.core import mail
from django.template.defaultfilters import date, floatformat
from django.urls import reverse
from django.utils.http import urlencode

from timary.models import Invoice, SentInvoice
from timary.templatetags.filters import nextmonday
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
    def extract_html(cls):
        s = mail.outbox[0].message().as_string()
        start = s.find("<body>") + len("<body>")
        end = s.find("</body>")
        message = s[start:end]
        return message

    @patch(
        "timary.services.stripe_service.StripeService.create_customer_for_invoice",
        return_value=None,
    )
    def test_create_invoice(self, customer_mock):
        Invoice.objects.all().delete()
        response = self.client.post(
            reverse("timary:create_invoice"),
            {
                "title": "Some title",
                "invoice_rate": 50,
                "invoice_type": 1,
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
            <h2 class="text-3xl font-bold mr-4">{invoice.title}</h2>
            """,
            response.content.decode("utf-8"),
        )
        self.assertIn(
            f"{inv_name} - {inv_email}",
            response.content.decode("utf-8"),
        )
        self.assertIn(
            f'{invoice.next_date.strftime("%b. %-d, %Y")}',
            response.content.decode("utf-8"),
        )
        self.assertEqual(response.templates[0].name, "partials/_invoice.html")
        self.assertEqual(response.status_code, 200)

    @patch(
        "timary.services.stripe_service.StripeService.create_customer_for_invoice",
        return_value=None,
    )
    def test_create_invoice_milestone(self, customer_mock):
        Invoice.objects.all().delete()
        response = self.client.post(
            reverse("timary:create_invoice"),
            {
                "title": "Some title",
                "invoice_rate": 50,
                "invoice_type": 2,
                "milestone_total_steps": 3,
                "email_recipient_name": "John Smith",
                "email_recipient": "john@test.com",
            },
        )
        invoice = Invoice.objects.first()
        self.assertInHTML(
            f"""
                <div class="grid grid-cols-1 sm:grid-cols-4 items-baseline my-5">
                <ul class="steps grow col-span-3">
                <li class="step step-primary">current</li><li class="step"></li><li class="step"></li>
                </ul>
                <a hx-get="{reverse("timary:generate_invoice", kwargs={"invoice_id": invoice.id})}"
                    hx-confirm="Are you sure you want to complete this milestone?"
                    hx-target="closest #some-title" hx-swap="innerHTML" class="btn btn-sm btn-secondary my-5"
                    _="on htmx:beforeRequest add .loading to me end on htmx:afterRequest remove .loading from me">
                    Complete current milestone
                </a>
                </div>
                """,
            response.content.decode("utf-8"),
        )
        self.assertEqual(response.templates[0].name, "partials/_invoice.html")
        self.assertEqual(response.status_code, 200)

    @patch(
        "timary.services.stripe_service.StripeService.create_customer_for_invoice",
        return_value=None,
    )
    def test_create_weekly_invoice(self, customer_mock):
        Invoice.objects.all().delete()
        response = self.client.post(
            reverse("timary:create_invoice"),
            {
                "title": "Some title",
                "invoice_type": 3,
                "weekly_rate": 1200,
                "email_recipient_name": "John Smith",
                "email_recipient": "john@test.com",
            },
        )
        invoice = Invoice.objects.first()
        inv_name = invoice.email_recipient_name
        inv_email = invoice.email_recipient
        self.assertIn(
            f"{inv_name} - {inv_email}",
            response.content.decode("utf-8"),
        )
        self.assertIn(
            nextmonday("").title(),
            response.content.decode("utf-8"),
        )
        self.assertEqual(response.templates[0].name, "partials/_invoice.html")
        self.assertEqual(response.status_code, 200)

    def test_manage_invoices(self):
        response = self.client.get(reverse("timary:manage_invoices"))
        self.assertInHTML(
            f'<h2 class="text-3xl font-bold mr-4">{self.invoice.title}</h2>',
            response.content.decode(),
        )
        self.assertIn(f"Hourly ${self.invoice.invoice_rate}", response.content.decode())
        self.assertTemplateUsed(response, "invoices/manage_invoices.html")
        self.assertEqual(response.status_code, 200)

    def test_manage_zero_invoices(self):
        Invoice.objects.filter(user=self.user).all().delete()
        response = self.client.get(reverse("timary:manage_invoices"))
        self.assertInHTML(
            """
            <div class="text-center lg:text-left md:mr-20">
                <h1 class="mb-5 text-3xl md:text-5xl font-bold" id="intro-text">
                    Hello there
                </h1>
                <p class="mb-5">
                    We all gotta start somewhere right? Begin your journey by adding your first invoicing details.
                </p>
            </div>
            """,
            response.content.decode("utf-8"),
        )
        self.assertTemplateUsed(response, "invoices/manage_invoices.html")
        self.assertEqual(response.status_code, 200)

    def test_zero_invoices_redirects_main_page(self):
        Invoice.objects.filter(user=self.user).all().delete()
        response = self.client.get(reverse("timary:index"))
        self.assertRedirects(response, reverse("timary:manage_invoices"))
        self.assertEqual(response.status_code, 302)

    @patch(
        "timary.services.stripe_service.StripeService.create_customer_for_invoice",
        return_value=None,
    )
    def test_create_invoice_error(self, customer_mock):
        invoice = self.user.get_invoices.first()
        response = self.client.post(
            reverse("timary:create_invoice"),
            {
                "title": invoice.title,
                "invoice_rate": 50,
                "invoice_type": 1,
                "invoice_interval": "D",
                "email_recipient_name": "John Smith",
                "email_recipient": "john@test.com",
            },
        )
        self.assertInHTML(
            "Duplicate invoice title not allowed.", response.content.decode("utf-8")
        )

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
            f"""<ul class="list-none">
                <li class="text-xl">{date(hour.date_tracked, "M jS")} - {floatformat(hour.hours, -2)} hrs </li>
           </ul>""",
            response.content.decode("utf-8"),
        )
        self.client.force_login(self.user)

    def test_view_invoice_stats(self):
        hour = DailyHoursFactory(invoice=self.invoice)
        response = self.client.get(
            reverse("timary:get_single_invoice", kwargs={"invoice_id": hour.invoice.id})
        )
        with self.assertRaises(AssertionError):
            self.assertInHTML(
                "View hours logged this period",
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

    def test_update_invoice(self):
        url_params = {
            "title": "Some title",
            "invoice_rate": 100,
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
            <h2 class="text-3xl font-bold mr-4">{self.invoice.title}</h2>
            """,
            response.content.decode("utf-8"),
        )
        self.assertIn(
            f"Hourly ${self.invoice.invoice_rate}",
            response.content.decode("utf-8"),
        )
        self.assertIn(
            f"{inv_name} - {inv_email}",
            response.content.decode("utf-8"),
        )
        self.assertIn(
            self.invoice.next_date.strftime("%b. %-d, %Y"),
            response.content.decode("utf-8"),
        )
        self.assertEqual(response.templates[0].name, "partials/_invoice.html")
        self.assertEqual(response.status_code, 200)

    def test_update_invoice_milestone(self):
        invoice = InvoiceFactory(invoice_type=2, user=self.user, milestone_step=3)
        url_params = {
            "title": "Some title",
            "invoice_rate": 100,
            "milestone_total_steps": 5,
            "email_recipient_name": "John Smith",
            "email_recipient": "john@test.com",
        }
        response = self.client.put(
            reverse("timary:update_invoice", kwargs={"invoice_id": invoice.id}),
            data=urlencode(url_params),  # HTML PUT FORM
        )
        invoice.refresh_from_db()
        self.assertInHTML(
            f"""
            <div class="grid grid-cols-1 sm:grid-cols-4 items-baseline my-5">
            <ul class="steps grow col-span-3">
            <li class="step step-primary"></li>
            <li class="step step-primary"></li>
            <li class="step step-primary">current</li>
            <li class="step"></li>
            <li class="step"></li>
            </ul>
            <a hx-get="{reverse("timary:generate_invoice", kwargs={"invoice_id": invoice.id})}"
                hx-confirm="Are you sure you want to complete this milestone?"
                hx-target="closest #some-title" hx-swap="innerHTML" class="btn btn-sm btn-secondary my-5"
                _="on htmx:beforeRequest add .loading to me end on htmx:afterRequest remove .loading from me">
                Complete current milestone
            </a>
            </div>
            """,
            response.content.decode("utf-8"),
        )
        self.assertEqual(response.templates[0].name, "partials/_invoice.html")
        self.assertEqual(response.status_code, 200)

    def test_update_weekly_invoice(self):
        invoice = InvoiceFactory(invoice_type=3, user=self.user, invoice_rate=50)
        url_params = {
            "title": "Some title",
            "weekly_rate": 100,
            "email_recipient_name": "John Smith",
            "email_recipient": "john@test.com",
        }
        response = self.client.put(
            reverse("timary:update_invoice", kwargs={"invoice_id": invoice.id}),
            data=urlencode(url_params),  # HTML PUT FORM
        )
        invoice.refresh_from_db()
        self.assertEqual(response.templates[0].name, "partials/_invoice.html")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(invoice.invoice_rate, 100)

    def test_update_invoice_dont_update_next_date_if_none(self):
        url_params = {
            "title": "Some title",
            "invoice_rate": 100,
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
        self.assertIn(
            "Paused",
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

    def test_pause_invoice_does_not_override_last_date(self):
        """
        Paused invoices shouldn't override the last date when unpaused
        since hours may be tracked prior and are not included in next sent invoice.
        """

        # Pause invoice
        invoice = InvoiceFactory(invoice_interval="M", user=self.user)
        hours1 = DailyHoursFactory(invoice=invoice)
        response = self.client.get(
            reverse("timary:pause_invoice", kwargs={"invoice_id": invoice.id}),
        )
        invoice.refresh_from_db()
        self.assertIsNone(invoice.next_date)
        self.assertEqual(response.templates[0].name, "partials/_invoice.html")
        self.assertEqual(response.status_code, 200)

        # Unpause invoice
        response = self.client.get(
            reverse("timary:pause_invoice", kwargs={"invoice_id": invoice.id}),
        )
        invoice.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, "partials/_invoice.html")
        self.assertEqual(
            invoice.next_date,
            datetime.date.today() + invoice.get_next_date(),
        )
        self.assertIn(hours1, invoice.get_hours_tracked())

    def test_pause_invoice_error(self):
        response = self.client.get(
            reverse(
                "timary:pause_invoice", kwargs={"invoice_id": self.invoice_no_user.id}
            ),
            data={},
        )
        self.assertEqual(response.status_code, 302)

    def test_archive_invoice(self):
        Invoice.objects.all().delete()
        invoice = InvoiceFactory(user=self.user)
        response = self.client.get(
            reverse("timary:archive_invoice", kwargs={"invoice_id": invoice.id}),
        )
        self.user.refresh_from_db()
        invoice.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(invoice.is_archived)
        self.assertEqual(self.user.get_invoices.count(), 0)

    def test_archive_invoice_error(self):
        response = self.client.get(
            reverse(
                "timary:archive_invoice", kwargs={"invoice_id": self.invoice_no_user.id}
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

    def test_dont_resend_invoice_email_if_not_active_subscription(self):
        invoice = InvoiceFactory()
        sent_invoice = SentInvoiceFactory(invoice=invoice, user=invoice.user)
        invoice.user.stripe_subscription_status = 3
        invoice.user.save()
        self.client.force_login(invoice.user)

        response = self.client.get(
            reverse(
                "timary:resend_invoice_email",
                kwargs={"sent_invoice_id": sent_invoice.id},
            ),
        )
        self.assertEqual(len(mail.outbox), 0)
        self.assertIn(
            "Your account is in-active. Please re-activate to resend an invoice",
            response.headers["HX-Trigger"],
        )
        self.client.logout()

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

    def test_total_invoice_stats(self):
        self.client.logout()
        self.client.force_login(self.user)

        hours1 = DailyHoursFactory(invoice__user=self.user)
        hours2 = DailyHoursFactory(invoice__user=self.user)
        s1 = SentInvoiceFactory(
            invoice=hours1.invoice,
            user=self.user,
            paid_status=SentInvoice.PaidStatus.PENDING,
        )
        s2 = SentInvoiceFactory(
            invoice=hours2.invoice,
            user=self.user,
            paid_status=SentInvoice.PaidStatus.PAID,
        )

        response = self.client.get(
            reverse(
                "timary:manage_invoices",
            ),
        )

        self.assertInHTML(
            f"""
            <div class="stats shadow">
              <div class="stat place-items-center">
                <div class="stat-value">${floatformat(s1.total_price, -2) }</div>
                <div class="stat-desc">owed</div>
              </div>

              <div class="stat place-items-center">
                <div class="stat-value">${ floatformat(s2.total_price, -2) }</div>
                <div class="stat-desc">total earned</div>
              </div>
            </div>""",
            response.content.decode("utf-8"),
        )

    def test_dont_generate_invoice_if_not_active_subscription(self):
        hours = DailyHoursFactory()
        hours.invoice.user.stripe_subscription_status = 3
        hours.invoice.user.save()
        self.client.force_login(hours.invoice.user)
        response = self.client.get(
            reverse("timary:generate_invoice", kwargs={"invoice_id": hours.invoice.id}),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Your account is in-active. Please re-activate to generate an invoice",
            response.headers["HX-Trigger"],
        )

        self.assertEquals(len(mail.outbox), 0)
        self.client.logout()

    def test_generate_invoice(self):
        todays_date = datetime.date.today()
        current_month = datetime.date.strftime(todays_date, "%m/%Y")
        hours = DailyHoursFactory(invoice=self.invoice)
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("timary:generate_invoice", kwargs={"invoice_id": self.invoice.id}),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEquals(len(mail.outbox), 1)
        self.assertEquals(
            mail.outbox[0].subject,
            f"{hours.invoice.title}'s Invoice from {hours.invoice.user.first_name} for {current_month}",
        )
        self.assertTemplateUsed(response, "partials/_invoice.html")

    def test_generate_invoice_milestone(self):
        invoice = InvoiceFactory(
            invoice_type=Invoice.InvoiceType.MILESTONE,
            milestone_step=3,
            milestone_total_steps=6,
            user=self.user,
        )
        DailyHoursFactory(invoice=invoice)
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("timary:generate_invoice", kwargs={"invoice_id": invoice.id}),
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.milestone_step, 4)
        self.assertEqual(response.status_code, 200)
        self.assertEquals(len(mail.outbox), 1)

    def test_get_hour_forms_for_invoice(self):
        """Only hours1 and hours2 show since its date_tracked
        is within invoice's last date and current date"""
        hours1 = DailyHoursFactory(invoice=self.invoice)
        hours2 = DailyHoursFactory(invoice=self.invoice)
        hours3 = DailyHoursFactory(
            invoice=self.invoice,
            date_tracked=datetime.date.today() - relativedelta(months=2),
        )
        response = self.client.get(
            reverse("timary:edit_invoice_hours", kwargs={"invoice_id": self.invoice.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, "partials/_edit_hours.html")
        self.assertInHTML(
            f"""
            <input type="text" name="hours" value="{str(round(hours1.hours, 2))}" value="1.0"
            class="input input-bordered border-2 text-lg hours-input w-full"
            _="on input call filterHoursInput(me) end on blur call convertHoursInput(me) end" required id="id_hours">
            """,
            response.content.decode("utf-8"),
        )
        self.assertInHTML(
            f"""
            <input type="text" name="hours" value="{str(round(hours2.hours, 2))}" value="1.0"
            class="input input-bordered border-2 text-lg hours-input w-full"
            _="on input call filterHoursInput(me) end on blur call convertHoursInput(me) end" required id="id_hours">
            """,
            response.content.decode("utf-8"),
        )
        self.assertNotIn(
            f"""
            <input type="text" name="hours" value="{str(round(hours3.hours, 2))}" value="1.0"
            class="input input-bordered border-2 text-lg hours-input w-full"
            _="on input call filterHoursInput(me) end on blur call convertHoursInput(me) end" required id="id_hours">
            """,
            response.content.decode("utf-8"),
        )

    def test_dont_sync_sent_invoice_if_not_active_subscription(self):
        hours = DailyHoursFactory()
        hours.invoice.user.stripe_subscription_status = 3
        hours.invoice.user.save()
        sent_invoice = SentInvoiceFactory(
            invoice=hours.invoice, user=hours.invoice.user
        )
        self.client.force_login(hours.invoice.user)
        response = self.client.get(
            reverse(
                "timary:sync_sent_invoice", kwargs={"sent_invoice_id": sent_invoice.id}
            ),
        )

        self.assertIn(
            "Your account is in-active. Please re-activate to sync your invoice",
            response.headers["HX-Trigger"],
        )
        self.assertTemplateUsed(response, "partials/_sent_invoice.html")

        self.client.logout()

    @patch("timary.services.accounting_service.AccountingService.create_invoice")
    def test_sync_sent_invoice(self, create_invoice_mock):
        create_invoice_mock.return_value = None
        self.user.accounting_org = "quickbooks"
        self.user.accounting_org_id = "abc123"
        self.user.save()
        sent_invoice = SentInvoiceFactory(
            invoice=self.invoice,
            user=self.user,
            paid_status=SentInvoice.PaidStatus.PAID,
        )
        self.client.force_login(self.user)
        response = self.client.get(
            reverse(
                "timary:sync_sent_invoice", kwargs={"sent_invoice_id": sent_invoice.id}
            ),
        )
        self.assertIn(
            f"{sent_invoice.invoice.title} is now synced with {sent_invoice.invoice.user.accounting_org.title()}",
            response.headers["HX-Trigger"],
        )
        self.assertTemplateUsed(response, "partials/_sent_invoice.html")

    def test_sync_sent_invoice_error_no_paid(self):
        sent_invoice = SentInvoiceFactory(
            invoice=self.invoice,
            user=self.user,
            paid_status=SentInvoice.PaidStatus.PENDING,
        )
        response = self.client.get(
            reverse(
                "timary:sync_sent_invoice", kwargs={"sent_invoice_id": sent_invoice.id}
            ),
        )
        self.assertIn(
            "Invoice isn't paid",
            response.headers["HX-Trigger"],
        )
        self.assertTemplateUsed(response, "partials/_sent_invoice.html")

    def test_sync_sent_invoice_error_no_accounting_service(self):
        sent_invoice = SentInvoiceFactory(
            invoice=self.invoice,
            user=self.user,
            paid_status=SentInvoice.PaidStatus.PAID,
        )
        response = self.client.get(
            reverse(
                "timary:sync_sent_invoice", kwargs={"sent_invoice_id": sent_invoice.id}
            ),
        )
        self.assertIn(
            "No accounting service found",
            response.headers["HX-Trigger"],
        )
        self.assertTemplateUsed(response, "partials/_sent_invoice.html")
