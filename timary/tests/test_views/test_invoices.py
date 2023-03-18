import copy
import uuid
import zoneinfo
from unittest.mock import patch

from dateutil.relativedelta import relativedelta
from django.contrib.messages import get_messages
from django.core import mail
from django.template.defaultfilters import date as template_date
from django.template.defaultfilters import floatformat
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode

from timary.models import (
    Invoice,
    LineItem,
    MilestoneInvoice,
    SentInvoice,
    SingleInvoice,
    User,
)
from timary.templatetags.filters import nextmonday
from timary.tests.factories import (
    ClientFactory,
    HoursLineItemFactory,
    IntervalInvoiceFactory,
    LineItemFactory,
    MilestoneInvoiceFactory,
    SentInvoiceFactory,
    SingleInvoiceFactory,
    UserFactory,
    WeeklyInvoiceFactory,
)
from timary.tests.test_views.basetest import BaseTest
from timary.utils import get_users_localtime


class TestRecurringInvoices(BaseTest):
    def setUp(self) -> None:
        super().setUp()

        self.user = UserFactory()
        self.client.force_login(self.user)
        self.invoice = IntervalInvoiceFactory(user=self.user)
        self.invoice_no_user = IntervalInvoiceFactory()

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
        fake_client = ClientFactory(user=self.user)
        response = self.client.post(
            reverse("timary:create_invoice"),
            {
                "title": "Some title",
                "rate": 50,
                "invoice_type": "interval",
                "invoice_interval": "W",
                "client": fake_client.id,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, "invoices/interval/_card.html")

        invoice = Invoice.objects.first()
        self.assertInHTML(
            f"""
            <h2 class="text-3xl font-bold overflow-x-hidden">{invoice.title}</h2>
            """,
            response.content.decode("utf-8"),
        )
        self.assertIn(
            fake_client.name,
            response.content.decode("utf-8"),
        )
        local_date = invoice.next_date.astimezone(
            tz=zoneinfo.ZoneInfo("America/New_York")
        )
        self.assertIn(
            f"<span>{template_date(local_date, 'M. j, Y')}</span>",
            response.content.decode("utf-8"),
        )

    @patch(
        "timary.services.stripe_service.StripeService.create_customer_for_invoice",
        return_value=None,
    )
    def test_create_invoice_milestone(self, customer_mock):
        Invoice.objects.all().delete()
        fake_client = ClientFactory()
        response = self.client.post(
            reverse("timary:create_invoice"),
            {
                "title": "Some title",
                "rate": 50,
                "invoice_type": "milestone",
                "milestone_total_steps": 3,
                "client": fake_client.id,
            },
        )
        invoice = MilestoneInvoice.objects.first()
        self.assertInHTML(
            f"""
                <div class="grid grid-cols-1 sm:grid-cols-4 items-baseline my-5">
                <ul class="steps grow col-span-3">
                <li class="step step-primary">current</li><li class="step"></li><li class="step"></li>
                </ul>
                <a hx-get="{reverse("timary:generate_invoice", kwargs={"invoice_id": invoice.id})}"
                    hx-confirm="Are you sure you want to complete this milestone?"
                    hx-target="closest #some-title" hx-swap="outerHTML" class="btn btn-ghost btn-outline my-5"
                    _="on htmx:beforeRequest add .loading to me end on htmx:afterRequest remove .loading from me">
                    Complete milestone
                </a>
                </div>
                """,
            response.content.decode("utf-8"),
        )
        self.assertEqual(response.templates[0].name, "invoices/milestone/_card.html")
        self.assertEqual(response.status_code, 200)

    @patch(
        "timary.services.stripe_service.StripeService.create_customer_for_invoice",
        return_value=None,
    )
    def test_create_weekly_invoice(self, customer_mock):
        Invoice.objects.all().delete()
        fake_client = ClientFactory()
        response = self.client.post(
            reverse("timary:create_invoice"),
            {
                "title": "Some title",
                "invoice_type": "weekly",
                "rate": 1200,
                "client": fake_client.id,
            },
        )
        self.assertIn(
            fake_client.name,
            response.content.decode("utf-8"),
        )
        date = timezone.now().astimezone(tz=zoneinfo.ZoneInfo("America/New_York"))
        formatted_date = template_date(date, "c")
        self.assertIn(
            nextmonday(
                field="",
                today_str=formatted_date,
            ).title(),
            response.content.decode("utf-8"),
        )
        self.assertEqual(response.templates[0].name, "invoices/weekly/_card.html")
        self.assertEqual(response.status_code, 200)

    def test_manage_invoices(self):
        response = self.client.get(reverse("timary:manage_invoices"))
        self.assertInHTML(
            f'<h2 class="text-3xl font-bold overflow-x-hidden">{self.invoice.title}</h2>',
            response.content.decode(),
        )
        self.assertIn(f"Hourly ${self.invoice.rate}", response.content.decode())
        self.assertTemplateUsed(response, "invoices/manage_invoices.html")
        self.assertEqual(response.status_code, 200)

    def test_manage_zero_invoices(self):
        Invoice.objects.filter(user=self.user).all().delete()
        response = self.client.get(reverse("timary:manage_invoices"))
        self.assertIn(
            "Get Started",  # Intro text
            response.content.decode("utf-8"),
        )
        self.assertIn(
            "We all gotta start somewhere right? Begin your journey by adding your first invoicing details.",
            response.content.decode("utf-8"),
        )
        self.assertTemplateUsed(response, "invoices/manage_invoices.html")
        self.assertEqual(response.status_code, 200)

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
                "rate": 50,
                "invoice_type": "interval",
                "invoice_interval": "W",
                "client_name": "John Smith",
                "client_email": "john@test.com",
            },
        )
        self.assertInHTML(
            "Duplicate invoice title not allowed.", response.content.decode("utf-8")
        )

    def test_get_invoice(self):
        rendered_template = self.setup_template(
            "invoices/interval/_card.html", {"invoice": self.invoice}
        )
        response = self.client.get(
            reverse("timary:get_single_invoice", kwargs={"invoice_id": self.invoice.id})
        )
        self.assertHTMLEqual(rendered_template, response.content.decode("utf-8"))

    def test_get_invoice_with_hours_logged(self):
        hour = HoursLineItemFactory(invoice=self.invoice)

        rendered_template = self.setup_template(
            "invoices/interval/_card.html", {"invoice": self.invoice}
        )
        response = self.client.get(
            reverse("timary:get_single_invoice", kwargs={"invoice_id": self.invoice.id})
        )
        self.assertHTMLEqual(rendered_template, response.content.decode("utf-8"))
        local_date = hour.date_tracked.astimezone(
            tz=zoneinfo.ZoneInfo(self.invoice.user.timezone)
        )
        self.assertInHTML(
            f"""
            <li class="flex justify-between text-xl">
                <span>{template_date(local_date, "M j")}</span>
                <span>{floatformat(hour.quantity, -2)} hrs </span>
            </li>
           """,
            response.content.decode("utf-8"),
        )
        self.client.force_login(self.user)

    def test_view_invoice_stats(self):
        hour = HoursLineItemFactory(invoice=self.invoice)
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
        fake_client = ClientFactory()
        url_params = {
            "title": "Some title",
            "rate": 100,
            "invoice_interval": "W",
            "client": fake_client.id,
        }
        response = self.client.put(
            reverse("timary:update_invoice", kwargs={"invoice_id": self.invoice.id}),
            data=urlencode(url_params),  # HTML PUT FORM
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, "invoices/interval/_card.html")
        self.invoice.refresh_from_db()
        self.assertInHTML(
            f"""
            <h2 class="text-3xl font-bold overflow-x-hidden">{self.invoice.title}</h2>
            """,
            response.content.decode("utf-8"),
        )
        self.assertIn(
            f"Hourly ${floatformat(self.invoice.rate, -2)}",
            response.content.decode("utf-8"),
        )
        self.assertIn(
            fake_client.name,
            response.content.decode("utf-8"),
        )
        self.assertIn(
            f"{template_date(self.invoice.next_date.astimezone(tz=zoneinfo.ZoneInfo('America/New_York')), 'M. j, Y')}",
            response.content.decode("utf-8"),
        )

    def test_update_invoice_milestone(self):
        fake_client = ClientFactory()
        invoice = MilestoneInvoiceFactory(user=self.user, milestone_step=3)
        url_params = {
            "title": "Some title",
            "rate": 100,
            "milestone_total_steps": 5,
            "client": fake_client.id,
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
                hx-target="closest #some-title" hx-swap="outerHTML" class="btn btn-ghost btn-outline my-5"
                _="on htmx:beforeRequest add .loading to me end on htmx:afterRequest remove .loading from me">
                Complete milestone
            </a>
            </div>
            """,
            response.content.decode("utf-8"),
        )
        self.assertEqual(response.templates[0].name, "invoices/milestone/_card.html")
        self.assertEqual(response.status_code, 200)

    def test_update_weekly_invoice(self):
        fake_client = ClientFactory()
        invoice = WeeklyInvoiceFactory(user=self.user, rate=50)
        url_params = {"title": "Some title", "rate": 100, "client": fake_client.id}
        response = self.client.put(
            reverse("timary:update_invoice", kwargs={"invoice_id": invoice.id}),
            data=urlencode(url_params),  # HTML PUT FORM
        )
        invoice.refresh_from_db()
        self.assertEqual(response.templates[0].name, "invoices/weekly/_card.html")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(invoice.rate, 100)

    def test_update_invoice_next_date_manually(self):
        invoice = IntervalInvoiceFactory(user=self.user)
        next_date = (
            get_users_localtime(self.user) + timezone.timedelta(weeks=2)
        ).astimezone(tz=zoneinfo.ZoneInfo("America/New_York"))
        url_params = {f"start_on_{invoice.email_id}": next_date.strftime("%Y-%m-%d")}
        response = self.client.put(
            reverse(
                "timary:update_invoice_next_date", kwargs={"invoice_id": invoice.id}
            ),
            data=urlencode(url_params),  # HTML PUT FORM
        )
        invoice.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            invoice.next_date.astimezone(
                tz=zoneinfo.ZoneInfo("America/New_York")
            ).date(),
            next_date.date(),
        )

    def test_dont_update_invoice_next_date_less_than_today(self):
        invoice = IntervalInvoiceFactory(user=self.user)
        next_date = get_users_localtime(self.user) - timezone.timedelta(days=14)
        url_params = {f"start_on_{invoice.email_id}": next_date.strftime("%Y-%m-%d")}
        response = self.client.put(
            reverse(
                "timary:update_invoice_next_date", kwargs={"invoice_id": invoice.id}
            ),
            data=urlencode(url_params),  # HTML PUT FORM
        )
        self.invoice.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(self.invoice.next_date.date(), next_date.date())

    def test_update_invoice_dont_update_next_date_if_paused(self):
        url_params = {
            "title": "Some title",
            "rate": 100,
            "invoice_interval": "W",
            "client_name": "John Smith",
            "client_email": "john@test.com",
        }
        self.invoice.invoice_interval = "B"
        self.invoice.calculate_next_date()
        next_date = copy.copy(self.invoice.next_date)
        self.invoice.is_paused = True
        self.invoice.save()
        response = self.client.put(
            reverse("timary:update_invoice", kwargs={"invoice_id": self.invoice.id}),
            data=urlencode(url_params),  # HTML PUT FORM
        )
        self.invoice.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        # Invoice next date shouldn't change if invoice is paused
        self.assertEqual(self.invoice.next_date, next_date)

    def test_update_invoice_error(self):
        response = self.client.put(
            reverse(
                "timary:update_invoice", kwargs={"invoice_id": self.invoice_no_user.id}
            ),
            data={},
        )
        self.assertEqual(response.status_code, 302)

    def test_pause_invoice(self):
        invoice = IntervalInvoiceFactory(invoice_interval="M", user=self.user)
        invoice.update()
        response = self.client.get(
            reverse("timary:pause_invoice", kwargs={"invoice_id": invoice.id}),
        )
        invoice.refresh_from_db()
        self.assertTrue(invoice.is_paused)
        self.assertEqual(response.templates[0].name, "invoices/interval/_card.html")
        self.assertEqual(response.status_code, 200)

        response = self.client.get(
            reverse("timary:pause_invoice", kwargs={"invoice_id": invoice.id}),
        )
        invoice.refresh_from_db()

        now = timezone.now().astimezone(tz=zoneinfo.ZoneInfo("America/New_York"))
        self.assertEqual(
            invoice.next_date.astimezone(
                tz=zoneinfo.ZoneInfo("America/New_York")
            ).date(),
            (now + invoice.get_next_date()).date(),
        )
        self.assertEqual(response.templates[0].name, "invoices/interval/_card.html")
        self.assertEqual(response.status_code, 200)

    def test_pause_invoice_does_not_override_last_date(self):
        """
        Paused invoices shouldn't override the last date when unpaused
        since hours may be tracked prior and are not included in next sent invoice.
        """

        # Pause invoice
        invoice = IntervalInvoiceFactory(invoice_interval="M", user=self.user)
        invoice.update()
        hours1 = HoursLineItemFactory(invoice=invoice)
        response = self.client.get(
            reverse("timary:pause_invoice", kwargs={"invoice_id": invoice.id}),
        )
        invoice.refresh_from_db()
        self.assertTrue(invoice.next_date)
        self.assertEqual(response.templates[0].name, "invoices/interval/_card.html")
        self.assertEqual(response.status_code, 200)

        # Unpause invoice
        response = self.client.get(
            reverse("timary:pause_invoice", kwargs={"invoice_id": invoice.id}),
        )
        invoice.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, "invoices/interval/_card.html")
        now = timezone.now().astimezone(tz=zoneinfo.ZoneInfo("America/New_York"))
        self.assertEqual(
            invoice.next_date.astimezone(
                tz=zoneinfo.ZoneInfo("America/New_York")
            ).date(),
            (now + invoice.get_next_date()).date(),
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
        invoice = IntervalInvoiceFactory(user=self.user)
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
        invoice = IntervalInvoiceFactory(user=self.user)
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
        invoice = IntervalInvoiceFactory()
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
        invoice = IntervalInvoiceFactory(user=self.user)
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

        hours1 = HoursLineItemFactory(invoice__user=self.user)
        hours2 = HoursLineItemFactory(invoice__user=self.user)
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
                <div class="stat-value">${floatformat(s1.total_price, -2) }</div>
            """,
            response.content.decode("utf-8"),
        )
        self.assertInHTML(
            f"""
                <div class="stat-value">${floatformat(s2.total_price, -2)}</div>
            """,
            response.content.decode("utf-8"),
        )

    def test_total_invoice_stats_only_current_year(self):
        self.client.logout()
        self.client.force_login(self.user)

        hours1 = HoursLineItemFactory(invoice__user=self.user)
        hours2 = HoursLineItemFactory(invoice__user=self.user)
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
        s3 = SentInvoiceFactory(
            invoice=hours2.invoice,
            user=self.user,
            paid_status=SentInvoice.PaidStatus.PAID,
            date_sent=get_users_localtime(self.user) - relativedelta(years=1),
        )

        response = self.client.get(
            reverse(
                "timary:manage_invoices",
            ),
        )

        self.assertInHTML(
            f"""
                <div class="stat-value">${floatformat(s1.total_price, -2) }</div>
            """,
            response.content.decode("utf-8"),
        )
        # Only calculate sent invoices for current year
        self.assertNotIn(
            f"""
            <div class="stat-value">${floatformat((s2.total_price + s3.total_price), -2)}</div>
            """,
            response.content.decode("utf-8"),
        )
        self.assertInHTML(
            f"""
                <div class="stat-value">${floatformat(s2.total_price, -2)}</div>
            """,
            response.content.decode("utf-8"),
        )

    def test_dont_generate_invoice_if_not_active_subscription(self):
        hours = HoursLineItemFactory()
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
        hours = HoursLineItemFactory(invoice=self.invoice)
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("timary:generate_invoice", kwargs={"invoice_id": self.invoice.id}),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEquals(len(mail.outbox), 1)
        self.assertEquals(
            mail.outbox[0].subject,
            f"{hours.invoice.title}'s Invoice from {hours.invoice.user.first_name} is ready to view.",
        )
        self.assertTemplateUsed(response, "invoices/interval/_card.html")

    def test_generate_invoice_milestone(self):
        invoice = MilestoneInvoiceFactory(
            milestone_step=3,
            milestone_total_steps=6,
            user=self.user,
        )
        HoursLineItemFactory(invoice=invoice)
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("timary:generate_invoice", kwargs={"invoice_id": invoice.id}),
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.milestone_step, 4)
        self.assertEqual(response.status_code, 200)
        self.assertEquals(len(mail.outbox), 1)

    def test_cannot_generate_invoice_if_paused(self):
        invoice = IntervalInvoiceFactory(is_paused=True, user=self.user)
        HoursLineItemFactory(invoice=invoice)
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("timary:generate_invoice", kwargs={"invoice_id": invoice.id}),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEquals(len(mail.outbox), 0)
        self.assertIn(
            "Cannot send an invoice while it is been paused", str(response.headers)
        )

    def test_get_hour_forms_for_invoice(self):
        """Only hours1 and hours2 show since its date_tracked
        is within invoice's last date and current date"""
        hours1 = HoursLineItemFactory(invoice=self.invoice)
        hours2 = HoursLineItemFactory(invoice=self.invoice)
        hours3 = HoursLineItemFactory(
            invoice=self.invoice,
            date_tracked=timezone.now() - relativedelta(months=2),
        )
        response = self.client.get(
            reverse("timary:edit_invoice_hours", kwargs={"invoice_id": self.invoice.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, "partials/_edit_hours.html")
        self.assertInHTML(
            f"""
            <input type="text" name="quantity" value="{str(round(hours1.quantity, 2))}" value="1.0"
            class="input input-bordered border-2 text-lg hours-input w-full placeholder-gray-500"
            _="on input call filterHoursInput(me) end on blur call convertHoursInput(me) end"
            required id="id_{hours1.slug_id}">
            """,
            response.content.decode("utf-8"),
        )
        self.assertInHTML(
            f"""
            <input type="text" name="quantity" value="{str(round(hours2.quantity, 2))}" value="1.0"
            class="input input-bordered border-2 text-lg hours-input w-full placeholder-gray-500"
            _="on input call filterHoursInput(me) end on blur call convertHoursInput(me) end"
            required id="id_{hours2.slug_id}">
            """,
            response.content.decode("utf-8"),
        )
        self.assertNotIn(
            f"""
            <input type="text" name="quantity" value="{str(round(hours3.quantity, 2))}" value="1.0"
            class="input input-bordered border-2 text-lg hours-input w-full placeholder-gray-500"
            _="on input call filterHoursInput(me) end on blur call convertHoursInput(me) end"
            required id="id_{hours3.slug_id}">
            """,
            response.content.decode("utf-8"),
        )

    def test_dont_sync_sent_invoice_if_not_active_subscription(self):
        hours = HoursLineItemFactory()
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

    def test_sync_sent_invoice_error_no_active_subscription(self):
        user = UserFactory(
            stripe_subscription_status=User.StripeSubscriptionStatus.INACTIVE
        )
        sent_invoice = SentInvoiceFactory(
            invoice=self.invoice,
            user=user,
            paid_status=SentInvoice.PaidStatus.PAID,
        )
        self.client.force_login(user)
        response = self.client.get(
            reverse(
                "timary:sync_sent_invoice", kwargs={"sent_invoice_id": sent_invoice.id}
            ),
        )
        self.assertIn(
            "Your account is in-active. Please re-activate to sync your invoices.",
            response.headers["HX-Trigger"],
        )
        self.assertTemplateUsed(response, "partials/_sent_invoice.html")

    def test_cancel_invoice(self):
        sent_invoice = SentInvoiceFactory(
            invoice=self.invoice,
            user=self.user,
        )
        response = self.client.get(
            reverse(
                "timary:cancel_invoice", kwargs={"sent_invoice_id": sent_invoice.id}
            ),
        )
        sent_invoice.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(sent_invoice.paid_status, SentInvoice.PaidStatus.CANCELLED)

    def test_edit_sent_invoice_hours(self):
        invoice = IntervalInvoiceFactory(user=self.user)
        sent_invoice = SentInvoiceFactory(invoice=invoice, user=self.user)
        hour1 = HoursLineItemFactory(invoice=invoice, date_tracked=invoice.last_date)
        hour1.sent_invoice_id = sent_invoice.id
        hour1.save()
        response = self.client.put(
            reverse(
                "timary:edit_sent_invoice_hours",
                kwargs={"sent_invoice_id": sent_invoice.id},
            )
        )
        self.assertIn("Sent updated invoice", str(response.headers))

    def test_edit_sent_invoice_hours_including_archived_invoics(self):
        invoice = IntervalInvoiceFactory(user=self.user, is_archived=True)
        sent_invoice = SentInvoiceFactory(invoice=invoice, user=self.user)
        hour1 = HoursLineItemFactory(invoice=invoice, date_tracked=invoice.last_date)
        hour1.sent_invoice_id = sent_invoice.id
        hour1.save()
        response = self.client.put(
            reverse(
                "timary:edit_sent_invoice_hours",
                kwargs={"sent_invoice_id": sent_invoice.id},
            )
        )
        self.assertIn("Sent updated invoice", str(response.headers))

    def test_edit_sent_invoice_hours_update_single_hour(self):
        invoice = IntervalInvoiceFactory(user=self.user)
        sent_invoice = SentInvoiceFactory(invoice=invoice, user=self.user)
        hour1 = HoursLineItemFactory(
            invoice=invoice, date_tracked=invoice.last_date, quantity=10
        )
        hour1.sent_invoice_id = sent_invoice.id
        hour1.save()

        url_params = {
            "quantity": hour1.quantity,
            "invoice": invoice.id,
            "hour_id": hour1.id,
        }
        response = self.client.patch(
            reverse(
                "timary:edit_sent_invoice_hours",
                kwargs={"sent_invoice_id": sent_invoice.id},
            ),
            data=urlencode(url_params),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Successfully updated hours!", response.content.decode("utf-8"))

    def test_edit_sent_invoice_hours_update_single_errors(self):
        invoice = IntervalInvoiceFactory(user=self.user)
        sent_invoice = SentInvoiceFactory(invoice=invoice, user=self.user)
        hour1 = HoursLineItemFactory(invoice=invoice, date_tracked=invoice.last_date)
        hour1.sent_invoice_id = sent_invoice.id
        hour1.save()

        url_params = {
            "quantity": -2,
            "invoice": invoice.id,
            "hour_id": hour1.id,
        }
        response = self.client.patch(
            reverse(
                "timary:edit_sent_invoice_hours",
                kwargs={"sent_invoice_id": sent_invoice.id},
            ),
            data=urlencode(url_params),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Invalid hours logged. Please log between 0 and 24 hours",
            response.content.decode("utf-8"),
        )

    def test_edit_sent_invoice_hours_invalid_hour_id(self):
        invoice = IntervalInvoiceFactory(user=self.user)
        sent_invoice = SentInvoiceFactory(invoice=invoice, user=self.user)
        url_params = {
            "quantity": -2,
            "invoice": invoice.id,
            "hour_id": uuid.uuid4(),
        }
        response = self.client.patch(
            reverse(
                "timary:edit_sent_invoice_hours",
                kwargs={"sent_invoice_id": sent_invoice.id},
            ),
            data=urlencode(url_params),
        )
        self.assertEqual(response.status_code, 302)  # Redirect to login page if invalid

    def test_edit_sent_invoice_hours_delete_single_hour(self):
        invoice = IntervalInvoiceFactory(user=self.user, rate=125)
        sent_invoice = SentInvoiceFactory(
            invoice=invoice, user=self.user, hourly_rate_snapshot=125
        )
        hour1 = HoursLineItemFactory(invoice=invoice, date_tracked=invoice.last_date)
        hour1.sent_invoice_id = sent_invoice.id
        hour1.save()
        hour2 = HoursLineItemFactory(invoice=invoice, date_tracked=invoice.last_date)
        hour2.sent_invoice_id = sent_invoice.id
        hour2.save()
        sent_invoice.update_total_price()
        expected_sent_invoice_total_price = sent_invoice.total_price - (
            hour1.quantity * invoice.rate
        )
        self.client.delete(
            f'{reverse("timary:edit_sent_invoice_hours",kwargs={"sent_invoice_id": sent_invoice.id})}'
            f"?hour_id={hour1.id}",
        )
        self.assertEqual(
            expected_sent_invoice_total_price, hour2.quantity * invoice.rate
        )

    def test_edit_sent_invoice_hours_cannot_delete_single_hour_remaining(self):
        invoice = IntervalInvoiceFactory(user=self.user)
        sent_invoice = SentInvoiceFactory(invoice=invoice, user=self.user)
        hour1 = HoursLineItemFactory(invoice=invoice, date_tracked=invoice.last_date)
        hour1.sent_invoice_id = sent_invoice.id
        hour1.save()
        response = self.client.delete(
            f'{reverse("timary:edit_sent_invoice_hours",kwargs={"sent_invoice_id": sent_invoice.id},)}'
            f"?hour_id={hour1.id}",
        )
        self.assertIn(
            "The sent invoice needs at least one line item.", str(response.headers)
        )

    def test_edit_sent_invoice_hours_update_total_price(self):
        invoice = IntervalInvoiceFactory(user=self.user, rate=20)
        sent_invoice = SentInvoiceFactory(
            invoice=invoice, user=self.user, hourly_rate_snapshot=20
        )
        hour1 = HoursLineItemFactory(invoice=invoice, date_tracked=invoice.last_date)
        hour1.sent_invoice_id = sent_invoice.id
        hour1.save()
        invoice.rate = 50
        invoice.save()
        response = self.client.put(
            reverse(
                "timary:edit_sent_invoice_hours",
                kwargs={"sent_invoice_id": sent_invoice.id},
            ),
        )
        self.assertEqual(response.status_code, 200)
        sent_invoice.refresh_from_db()
        self.assertEqual(
            sent_invoice.total_price, hour1.quantity * sent_invoice.hourly_rate_snapshot
        )

    def test_cannot_edit_sent_invoice_hours_if_not_started_yet(self):
        invoice = IntervalInvoiceFactory(user=self.user)
        sent_invoice = SentInvoiceFactory(
            invoice=invoice, user=self.user, paid_status=2
        )
        hour1 = HoursLineItemFactory(invoice=invoice, date_tracked=invoice.last_date)
        hour1.sent_invoice_id = sent_invoice.id
        hour1.save()
        response = self.client.put(
            reverse(
                "timary:edit_sent_invoice_hours",
                kwargs={"sent_invoice_id": sent_invoice.id},
            ),
        )
        self.assertEqual(response.status_code, 200)
        sent_invoice.refresh_from_db()
        self.assertIn("Unable to edit hours", str(response.headers))


class TestSingleInvoices(BaseTest):
    def setUp(self) -> None:
        super().setUp()

        self.user = UserFactory()
        self.client.force_login(self.user)

    @classmethod
    def extract_html(cls):
        s = mail.outbox[0].message().as_string()
        start = s.find("<body>") + len("<body>")
        end = s.find("</body>")
        message = s[start:end]
        return message

    def test_create_invoice(self):
        Invoice.objects.all().delete()
        fake_client = ClientFactory()
        response = self.client.post(
            reverse("timary:single_invoice"),
            {"title": "Some title", "client": fake_client.id},
        )

        invoice = SingleInvoice.objects.first()
        self.assertRedirects(
            response,
            reverse(
                "timary:update_single_invoice", kwargs={"single_invoice_id": invoice.id}
            ),
            fetch_redirect_response=True,
        )
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), f"Successfully created {invoice.title}")

    def test_create_invoice_single_line_item(self):
        Invoice.objects.all().delete()
        fake_client = ClientFactory()
        self.client.post(
            reverse("timary:single_invoice"),
            {
                "title": "Some title",
                "client": fake_client.id,
                "id": "",
                "description": "Test",
                "quantity": 1,
                "unit_price": 2.5,
            },
        )

        invoice = SingleInvoice.objects.first()
        self.assertEqual(invoice.line_items.count(), 1)
        self.assertEqual(invoice.balance_due, 2.5)

    def test_create_invoice_multiple_line_items(self):
        Invoice.objects.all().delete()
        fake_client = ClientFactory()

        self.client.post(
            reverse("timary:single_invoice"),
            {
                "title": "Some title",
                "client": fake_client.id,
                "id": ["", ""],
                "description": ["Test", "Test2"],
                "quantity": [1, 2],
                "unit_price": [2.5, 3],
            },
        )

        invoice = SingleInvoice.objects.first()
        self.assertEqual(invoice.line_items.count(), 2)
        self.assertEqual(invoice.balance_due, 8.5)

    def test_create_invoice_error(self):
        fake_client = ClientFactory()
        response = self.client.post(
            reverse("timary:single_invoice"),
            {
                "title": "2Some title",
                "client": fake_client.id,
            },
        )
        self.assertIn(
            "Title cannot start with a number.", response.content.decode("utf-8")
        )
        self.assertEqual(SingleInvoice.objects.all().count(), 0)

    def test_update_invoice(self):
        fake_client = ClientFactory()
        invoice = SingleInvoiceFactory(user=self.user, client=fake_client)
        self.client.post(
            reverse(
                "timary:update_single_invoice", kwargs={"single_invoice_id": invoice.id}
            ),
            {"title": "Some title", "client": fake_client.id},
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.title, "Some title")

    def test_update_invoice_single_line_item(self):
        fake_client = ClientFactory()
        invoice = SingleInvoiceFactory(user=self.user, client=fake_client)
        line_item = LineItemFactory(invoice=invoice)
        response = self.client.post(
            reverse(
                "timary:update_single_invoice", kwargs={"single_invoice_id": invoice.id}
            ),
            {
                "title": "Some title",
                "client": fake_client.id,
                "id": line_item.id,
                "description": "Test",
                "quantity": 1,
                "unit_price": 2.5,
            },
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.balance_due, 2.5)
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(
            len(messages), 2
        )  # The second is the request to resend the invoice
        self.assertEqual(str(messages[0]), f"Updated {invoice.title}")

    def test_update_invoice_multiple_line_items(self):
        fake_client = ClientFactory()
        invoice = SingleInvoiceFactory(user=self.user, client=fake_client)
        line_item = LineItemFactory(invoice=invoice)
        second_line_item = LineItemFactory(invoice=invoice)
        self.client.post(
            reverse(
                "timary:update_single_invoice", kwargs={"single_invoice_id": invoice.id}
            ),
            {
                "title": "Some title",
                "client": fake_client.id,
                "id": [line_item.id, second_line_item.id],
                "description": ["Test", "Test2"],
                "quantity": [1, 2],
                "unit_price": [2.5, 3],
            },
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.balance_due, 8.5)

    def test_update_invoice_error(self):
        fake_client = ClientFactory()
        invoice = SingleInvoiceFactory(user=self.user, client=fake_client)
        line_item = LineItemFactory(invoice=invoice)
        response = self.client.post(
            reverse(
                "timary:update_single_invoice", kwargs={"single_invoice_id": invoice.id}
            ),
            {
                "title": "2Some title",
                "client": fake_client.id,
                "id": line_item.id,
                "description": "Test",
                "quantity": 1,
                "unit_price": 2.5,
            },
        )
        invoice.refresh_from_db()
        self.assertIn(
            "Title cannot start with a number.", response.content.decode("utf-8")
        )
        self.assertNotEqual(invoice.title, "2Some title")

    def test_delete_line_item(self):
        invoice = SingleInvoiceFactory(user=self.user)
        line_item = LineItemFactory(invoice=invoice)
        self.assertEqual(LineItem.objects.all().count(), 1)
        self.client.delete(
            f'{reverse("timary:single_invoice_line_item")}?line_item_id={line_item.id}',
        )
        self.assertEqual(LineItem.objects.all().count(), 0)

    def test_update_invoice_status_to_final(self):
        invoice = SingleInvoiceFactory(user=self.user, status=0)
        self.client.get(
            reverse(
                "timary:update_single_invoice_status",
                kwargs={"single_invoice_id": invoice.id},
            )
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, SingleInvoice.InvoiceStatus.FINAL)

    def test_update_invoice_status_to_draft(self):
        invoice = SingleInvoiceFactory(user=self.user, status=1)
        self.client.get(
            reverse(
                "timary:update_single_invoice_status",
                kwargs={"single_invoice_id": invoice.id},
            )
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, SingleInvoice.InvoiceStatus.DRAFT)

    def test_send_invoice_email(self):
        fake_client = ClientFactory()
        invoice = SingleInvoiceFactory(user=self.user, status=1, client=fake_client)
        line_item = LineItemFactory(invoice=invoice, quantity=1, unit_price=2.5)
        second_line_item = LineItemFactory(invoice=invoice, quantity=2, unit_price=3)
        invoice.update()
        self.client.get(
            reverse(
                "timary:send_single_invoice_email",
                kwargs={"single_invoice_id": invoice.id},
            )
        )
        invoice.refresh_from_db()

        html_message = TestSingleInvoices.extract_html()
        with self.subTest("Testing title"):
            msg = f"""
            <div class="mt-0 mb-4 text-3xl font-semibold text-left">Hi {fake_client.name},</div>
            <div class="my-2 text-xl leading-7">Thanks for using Timary.
            This is an invoice for {invoice.user.first_name}'s services.</div>
            """
            self.assertInHTML(msg, html_message)

        with self.subTest("Testing amount due"):
            msg = (
                f"<strong>Amount Due: "
                f"${floatformat(line_item.total_amount() + second_line_item.total_amount() + 5, -2)}</strong>"
            )
            self.assertInHTML(msg, html_message)

        with self.subTest("Testing line items"):
            msg = f"""
            <div>{line_item.description}</div>
            <div>${floatformat(line_item.total_amount(), -2)}</div>
            """
            self.assertInHTML(msg, html_message)

            msg = f"""
            <div>{second_line_item.description}</div>
            <div>${floatformat(second_line_item.total_amount(), -2)}</div>
            """
            self.assertInHTML(msg, html_message)

    def test_resend_invoice(self):
        """A single invoice should only have max 1 SentInvoice"""
        invoice = SingleInvoiceFactory(user=self.user, status=1)
        line_item = LineItemFactory(invoice=invoice, quantity=1, unit_price=2.5)
        second_line_item = LineItemFactory(invoice=invoice, quantity=2, unit_price=3)
        sent_invoice = SentInvoiceFactory(invoice=invoice)
        invoice.update()
        response = self.client.get(
            reverse(
                "timary:send_single_invoice_email",
                kwargs={"single_invoice_id": invoice.id},
            )
        )
        invoice.refresh_from_db()
        line_item.refresh_from_db()
        second_line_item.refresh_from_db()
        sent_invoice.refresh_from_db()
        self.assertEqual(sent_invoice.total_price, invoice.balance_due)
        self.assertEqual(invoice.invoice_snapshots.count(), 1)
        self.assertEqual(line_item.sent_invoice_id, str(sent_invoice.id))
        self.assertEqual(second_line_item.sent_invoice_id, str(sent_invoice.id))
        self.assertIn(
            f"Invoice for {invoice.title} has been sent",
            response.headers["HX-Trigger"],
        )

    def test_send_invoice_error_user_not_active(self):
        user = UserFactory(
            stripe_subscription_status=User.StripeSubscriptionStatus.INACTIVE
        )
        invoice = SingleInvoiceFactory(user=user, status=1)
        self.client.force_login(user)
        response = self.client.get(
            reverse(
                "timary:send_single_invoice_email",
                kwargs={"single_invoice_id": invoice.id},
            )
        )
        self.assertIn(
            "Unable to send out invoice.",
            response.headers["HX-Trigger"],
        )

    def test_send_invoice_error_invoice_is_draft(self):
        invoice = SingleInvoiceFactory(user=self.user, status=0)
        self.client.force_login(self.user)
        response = self.client.get(
            reverse(
                "timary:send_single_invoice_email",
                kwargs={"single_invoice_id": invoice.id},
            )
        )
        self.assertIn(
            "Unable to send out invoice.",
            response.headers["HX-Trigger"],
        )

    def test_send_invoice_error_invoice_is_paid(self):
        invoice = SingleInvoiceFactory(user=self.user, status=0)
        SentInvoiceFactory(invoice=invoice, paid_status=2)
        self.client.force_login(self.user)
        response = self.client.get(
            reverse(
                "timary:send_single_invoice_email",
                kwargs={"single_invoice_id": invoice.id},
            )
        )
        self.assertIn(
            "Unable to send out invoice.",
            response.headers["HX-Trigger"],
        )

    def test_send_first_invoice_installment(self):
        invoice = SingleInvoiceFactory(
            user=self.user, installments=3, status=1, balance_due=15
        )
        LineItemFactory(invoice=invoice, quantity=1, unit_price=15)
        response = self.client.get(
            reverse(
                "timary:send_invoice_installment",
                kwargs={"single_invoice_id": invoice.id},
            )
        )
        invoice.refresh_from_db()
        sent_invoice = invoice.get_sent_invoice().first()
        sent_invoice.refresh_from_db()
        self.assertIsNotNone(invoice.next_installment_date)
        self.assertEqual(sent_invoice.total_price, 5)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(
            f"Installment for {invoice.title} has been sent",
            response.headers["HX-Trigger"],
        )

    def test_do_not_send_first_invoice_installment_if_draft_status(self):
        invoice = SingleInvoiceFactory(
            user=self.user, installments=3, balance_due=15, status=0
        )
        LineItemFactory(invoice=invoice, quantity=1, unit_price=15)
        response = self.client.get(
            reverse(
                "timary:send_invoice_installment",
                kwargs={"single_invoice_id": invoice.id},
            )
        )
        invoice.refresh_from_db()
        sent_invoice = invoice.get_sent_invoice().first()
        self.assertIsNone(invoice.next_installment_date)
        self.assertIsNone(sent_invoice)
        self.assertEqual(len(mail.outbox), 0)
        self.assertIn(
            "Unable to send out invoice.",
            response.headers["HX-Trigger"],
        )

    def test_do_not_send_first_invoice_installment_if_already_has_first_installment(
        self,
    ):
        invoice = SingleInvoiceFactory(
            user=self.user, installments=3, balance_due=15, status=1
        )
        LineItemFactory(invoice=invoice, quantity=1, unit_price=15)
        SentInvoiceFactory(invoice=invoice)
        response = self.client.get(
            reverse(
                "timary:send_invoice_installment",
                kwargs={"single_invoice_id": invoice.id},
            )
        )
        invoice.refresh_from_db()
        self.assertIsNone(invoice.next_installment_date)
        self.assertEqual(len(mail.outbox), 0)
        self.assertIn(
            "Unable to send out invoice.",
            response.headers["HX-Trigger"],
        )
