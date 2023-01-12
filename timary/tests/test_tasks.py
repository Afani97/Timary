import datetime
from datetime import date
from unittest.mock import patch

from django.conf import settings
from django.core import mail
from django.template.defaultfilters import date as template_date
from django.template.defaultfilters import floatformat
from django.test import TestCase
from django.urls import reverse

from timary.models import HoursLineItem, SentInvoice
from timary.tasks import (
    gather_invoices,
    gather_recurring_hours,
    send_invoice,
    send_invoice_preview,
    send_weekly_updates,
)
from timary.tests.factories import (
    HoursLineItemFactory,
    InvoiceFactory,
    SentInvoiceFactory,
    UserFactory,
)
from timary.utils import get_date_parsed, get_starting_week_from_date


class TestGatherInvoices(TestCase):
    @patch("timary.tasks.async_task")
    def test_gather_0_invoices(self, send_invoice_mock):
        send_invoice_mock.return_value = None
        invoices_sent = gather_invoices()
        self.assertEqual("Invoices sent: 0", invoices_sent)
        self.assertEquals(
            mail.outbox[0].subject,
            "Sent out 0 invoices",
        )

    @patch("timary.tasks.async_task")
    def test_gather_0_invoices_for_today(self, send_invoice_mock):
        send_invoice_mock.return_value = None
        HoursLineItemFactory(
            invoice__next_date=datetime.date.today() + datetime.timedelta(days=2)
        )
        HoursLineItemFactory(
            invoice__next_date=datetime.date.today() - datetime.timedelta(days=1)
        )
        invoices_sent = gather_invoices()
        self.assertEqual("Invoices sent: 0", invoices_sent)
        self.assertEquals(
            mail.outbox[0].subject,
            "Sent out 0 invoices",
        )

    @patch("timary.tasks.async_task")
    def test_gather_0_invoices_with_next_date_null(self, send_invoice_mock):
        send_invoice_mock.return_value = None
        HoursLineItemFactory(invoice__next_date=None)
        HoursLineItemFactory()
        invoices_sent = gather_invoices()
        self.assertEqual("Invoices sent: 1", invoices_sent)
        self.assertEquals(
            mail.outbox[0].subject,
            "Sent out 1 invoices",
        )

    @patch("timary.tasks.async_task")
    def test_gather_1_invoice_for_today(self, send_invoice_mock):
        send_invoice_mock.return_value = None
        HoursLineItemFactory(
            invoice__next_date=datetime.date.today() + datetime.timedelta(days=2)
        )
        HoursLineItemFactory()
        invoices_sent = gather_invoices()
        self.assertEqual("Invoices sent: 1", invoices_sent)
        self.assertEquals(
            mail.outbox[0].subject,
            "Sent out 1 invoices",
        )

    @patch("timary.tasks.async_task")
    def test_gather_3_invoices_for_today(self, send_invoice_mock):
        send_invoice_mock.return_value = None
        HoursLineItemFactory()
        HoursLineItemFactory()
        HoursLineItemFactory()
        invoices_sent = gather_invoices()
        self.assertEqual("Invoices sent: 3", invoices_sent)
        self.assertEquals(
            mail.outbox[0].subject,
            "Sent out 3 invoices",
        )

    @patch("timary.tasks.async_task")
    def test_gather_1_invoice_preview_for_tomorrow(self, send_invoice_mock):
        send_invoice_mock.return_value = None
        HoursLineItemFactory(
            invoice__next_date=datetime.date.today() + datetime.timedelta(days=1)
        )
        invoices_sent = gather_invoices()
        self.assertEqual("Invoices sent: 1", invoices_sent)
        self.assertEquals(
            mail.outbox[0].subject,
            "Sent out 1 invoices",
        )

    @patch("timary.tasks.async_task")
    def test_gather_3_invoice_previews_for_tomorrow(self, send_invoice_mock):
        send_invoice_mock.return_value = None
        HoursLineItemFactory(
            invoice__next_date=datetime.date.today() + datetime.timedelta(days=1)
        )
        HoursLineItemFactory(
            invoice__next_date=datetime.date.today() + datetime.timedelta(days=1)
        )
        HoursLineItemFactory(
            invoice__next_date=datetime.date.today() + datetime.timedelta(days=1)
        )
        invoices_sent = gather_invoices()
        self.assertEqual("Invoices sent: 3", invoices_sent)
        self.assertEquals(
            mail.outbox[0].subject,
            "Sent out 3 invoices",
        )

    @patch("timary.tasks.async_task")
    def test_gather_1_invoice_and_invoice_previews(self, send_invoice_mock):
        send_invoice_mock.return_value = None
        HoursLineItemFactory()
        HoursLineItemFactory(
            invoice__next_date=datetime.date.today() + datetime.timedelta(days=1)
        )
        HoursLineItemFactory(
            invoice__next_date=datetime.date.today() + datetime.timedelta(days=2)
        )
        invoices_sent = gather_invoices()
        self.assertEqual("Invoices sent: 2", invoices_sent)
        self.assertEquals(
            mail.outbox[0].subject,
            "Sent out 2 invoices",
        )

    @patch("timary.tasks.async_task")
    def test_gather_1_invoice_and_not_milestone_invoice(self, send_invoice_mock):
        send_invoice_mock.return_value = None
        milestone_invoice = InvoiceFactory(invoice_type=2)
        HoursLineItemFactory(invoice=milestone_invoice)
        HoursLineItemFactory()
        invoices_sent = gather_invoices()
        self.assertEqual("Invoices sent: 1", invoices_sent)
        self.assertEquals(
            mail.outbox[0].subject,
            "Sent out 1 invoices",
        )

    @patch("timary.tasks.date")
    @patch("timary.tasks.async_task")
    def test_gather_1_invoice_monday_for_weekly(self, send_invoice_mock, today_mock):
        send_invoice_mock.return_value = None
        today_mock.today.return_value = datetime.date(2022, 8, 22)
        InvoiceFactory(invoice_type=3)
        invoices_sent = gather_invoices()
        self.assertEqual("Invoices sent: 1", invoices_sent)
        self.assertEquals(
            mail.outbox[0].subject,
            "Sent out 1 invoices",
        )

    @patch("timary.tasks.date")
    def test_gather_0_invoice_tuesday_for_weekly(self, today_mock):
        today_mock.today.return_value = datetime.date(2022, 8, 23)
        InvoiceFactory(invoice_type=3)
        invoices_sent = gather_invoices()
        self.assertEqual("Invoices sent: 0", invoices_sent)
        self.assertEquals(
            mail.outbox[0].subject,
            "Sent out 0 invoices",
        )


class TestGatherHours(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.start_week = get_starting_week_from_date(datetime.date.today()).isoformat()
        cls.next_week = get_starting_week_from_date(
            datetime.date.today() + datetime.timedelta(weeks=1)
        ).isoformat()

    def test_gather_0_hours(self):
        hours_added = gather_recurring_hours()
        self.assertEqual("0 hours added.", hours_added)
        self.assertEquals(HoursLineItem.objects.count(), 0)

    def test_gather_0_hours_with_archived_invoice(self):
        HoursLineItemFactory(
            recurring_logic={
                "type": "repeating",
                "interval": "d",
                "starting_week": self.start_week,
                "end_date": self.next_week,
            },
            invoice__is_archived=True,
        )
        hours_added = gather_recurring_hours()
        self.assertEqual("0 hours added.", hours_added)

    def test_gather_1_hour(self):
        HoursLineItemFactory(
            recurring_logic={
                "type": "repeating",
                "interval": "d",
                "starting_week": self.start_week,
                "end_date": self.next_week,
            }
        )
        hours_added = gather_recurring_hours()
        self.assertEqual("1 hours added.", hours_added)
        self.assertEquals(HoursLineItem.objects.count(), 2)

    def test_gather_2_hour(self):
        HoursLineItemFactory(
            recurring_logic={
                "type": "repeating",
                "interval": "d",
                "starting_week": self.start_week,
                "end_date": self.next_week,
            }
        )
        HoursLineItemFactory(
            recurring_logic={
                "type": "repeating",
                "interval": "w",
                "interval_days": [get_date_parsed(date.today())],
                "starting_week": self.start_week,
                "end_date": self.next_week,
            }
        )
        hours_added = gather_recurring_hours()
        self.assertEqual("2 hours added.", hours_added)
        self.assertEquals(HoursLineItem.objects.count(), 4)

    def test_passing_recurring_logic(self):
        hours = HoursLineItemFactory(
            recurring_logic={
                "type": "repeating",
                "interval": "d",
                "starting_week": self.start_week,
                "end_date": self.next_week,
            }
        )
        hours_added = gather_recurring_hours()
        self.assertEqual("1 hours added.", hours_added)
        self.assertEquals(HoursLineItem.objects.count(), 2)

        hours.refresh_from_db()
        self.assertIsNone(hours.recurring_logic)

    def test_hours_not_scheduled_do_not_get_created(self):
        hours = HoursLineItemFactory(
            recurring_logic={
                "type": "repeating",
                "interval": "w",
                "interval_days": [
                    get_date_parsed(date.today() - datetime.timedelta(days=1))
                ],
                "starting_week": self.start_week,
                "end_date": self.next_week,
            }
        )
        hours_added = gather_recurring_hours()
        self.assertEqual("0 hours added.", hours_added)
        self.assertEquals(HoursLineItem.objects.count(), 1)

        hours.refresh_from_db()
        self.assertIsNotNone(hours.recurring_logic)

    @patch("timary.models.HoursLineItem.update_recurring_starting_weeks")
    @patch("timary.tasks.date")
    def test_refresh_starting_weeks_on_saturday(self, date_mock, update_weeks_mock):
        date_mock.today.return_value = datetime.date(2022, 12, 31)
        date_mock.side_effect = lambda *args, **kw: datetime.date(*args, **kw)
        update_weeks_mock.return_value = None

        HoursLineItemFactory(
            recurring_logic={
                "type": "recurring",
                "interval": "b",
                "starting_week": get_starting_week_from_date(
                    date_mock.today()
                ).isoformat(),
                "interval_days": ["mon", "tue"],
            }
        )
        hours_added = gather_recurring_hours()
        self.assertEqual("0 hours added.", hours_added)
        self.assertEquals(HoursLineItem.objects.count(), 1)
        self.assertTrue(update_weeks_mock.assert_called_once)

    @patch("timary.models.HoursLineItem.cancel_recurring_hour")
    @patch("timary.tasks.date")
    def test_cancel_previous_recurring_logic(self, date_mock, cancel_hours_mock):
        """Prevent double stacking of hours, have one recurring instance at a time"""
        date_mock.today.return_value = datetime.date(2022, 12, 31)
        date_mock.side_effect = lambda *args, **kw: datetime.date(*args, **kw)
        cancel_hours_mock.return_value = None

        HoursLineItemFactory(
            recurring_logic={
                "type": "recurring",
                "interval": "d",
                "starting_week": self.start_week,
            }
        )
        hours_added = gather_recurring_hours()
        self.assertEqual("1 hours added.", hours_added)
        self.assertEquals(HoursLineItem.objects.count(), 2)
        self.assertTrue(cancel_hours_mock.assert_called_once)


class TestSendInvoice(TestCase):
    def setUp(self) -> None:
        self.todays_date = date.today()
        self.current_month = date.strftime(self.todays_date, "%m/%Y")

    @classmethod
    def extract_html(cls):
        s = mail.outbox[0].message().as_string()
        start = s.find("<body>") + len("<body>")
        end = s.find("</body>")
        message = s[start:end]
        return message

    def test_send_one_invoice(self):
        hours = HoursLineItemFactory()
        send_invoice(hours.invoice.id)
        self.assertEquals(len(mail.outbox), 1)
        self.assertEquals(
            mail.outbox[0].subject,
            f"{hours.invoice.title}'s Invoice from {hours.invoice.user.first_name} for {self.current_month}",
        )
        self.assertEquals(SentInvoice.objects.count(), 1)

    def test_sent_invoices_hours(self):
        two_days_ago = self.todays_date - datetime.timedelta(days=2)
        yesterday = self.todays_date - datetime.timedelta(days=1)
        invoice = InvoiceFactory(
            last_date=self.todays_date - datetime.timedelta(days=3)
        )
        h1 = HoursLineItemFactory(date_tracked=two_days_ago, invoice=invoice)
        h2 = HoursLineItemFactory(date_tracked=yesterday, invoice=invoice)
        h3 = HoursLineItemFactory(date_tracked=self.todays_date, invoice=invoice)

        send_invoice(invoice.id)
        self.assertEquals(len(mail.outbox), 1)
        self.assertEquals(SentInvoice.objects.count(), 1)

        sent_invoice = SentInvoice.objects.first()
        self.assertEquals(
            sent_invoice.total_price,
            (h1.quantity + h2.quantity + h3.quantity) * invoice.invoice_rate,
        )

    def test_sent_invoices_only_2_hours(self):
        yesterday = self.todays_date - datetime.timedelta(days=1)
        invoice = InvoiceFactory(
            last_date=self.todays_date - datetime.timedelta(days=1)
        )
        HoursLineItemFactory(
            date_tracked=self.todays_date - datetime.timedelta(days=2), invoice=invoice
        )
        h2 = HoursLineItemFactory(date_tracked=yesterday, invoice=invoice)
        h3 = HoursLineItemFactory(date_tracked=self.todays_date, invoice=invoice)

        send_invoice(invoice.id)
        self.assertEquals(len(mail.outbox), 1)
        self.assertEquals(SentInvoice.objects.count(), 1)

        sent_invoice = SentInvoice.objects.first()
        self.assertEquals(
            sent_invoice.total_price,
            (h2.quantity + h3.quantity) * invoice.invoice_rate,
        )

    def test_dont_send_invoice_if_no_tracked_hours(self):
        hours = HoursLineItemFactory(
            date_tracked=(self.todays_date - datetime.timedelta(days=1))
        )
        hours.invoice.last_date = self.todays_date
        hours.invoice.save()
        hours.save()

        send_invoice(hours.invoice.id)
        self.assertEqual(len(mail.outbox), 0)

        hours.invoice.refresh_from_db()
        self.assertEqual(
            hours.invoice.next_date, self.todays_date + hours.invoice.get_next_date()
        )
        self.assertEquals(SentInvoice.objects.count(), 0)

    def test_dont_send_invoice_if_skipped_hours(self):
        hours = HoursLineItemFactory(quantity=0)

        send_invoice(hours.invoice.id)

        hours_tracked, total_amount = hours.invoice.get_hours_stats()

        self.assertEqual(len(mail.outbox), 0)
        self.assertEquals(hours_tracked.count(), 0)
        self.assertEquals(total_amount, 0)
        self.assertEquals(SentInvoice.objects.count(), 0)

    def test_send_two_invoice_and_subjects(self):
        hours1 = HoursLineItemFactory()
        hours2 = HoursLineItemFactory()
        send_invoice(hours1.invoice.id)
        send_invoice(hours2.invoice.id)
        self.assertEquals(len(mail.outbox), 2)
        self.assertEquals(
            mail.outbox[0].subject,
            f"{hours1.invoice.title}'s Invoice from {hours1.invoice.user.first_name} for {self.current_month}",
        )
        self.assertEquals(
            mail.outbox[1].subject,
            f"{hours2.invoice.title}'s Invoice from {hours2.invoice.user.first_name} for {self.current_month}",
        )
        self.assertEquals(SentInvoice.objects.count(), 2)

    def test_invoice_context(self):
        invoice = InvoiceFactory(invoice_rate=25)
        # Save last date before it's updated in send_invoice method to test email contents below
        hours_1 = HoursLineItemFactory(invoice=invoice, quantity=1)
        HoursLineItemFactory(invoice=invoice, quantity=2)
        HoursLineItemFactory(invoice=invoice, quantity=3)

        send_invoice(invoice.id)
        invoice.refresh_from_db()

        html_message = TestSendInvoice.extract_html()
        with self.subTest("Testing title"):
            msg = f"""
            <div class="mt-0 mb-4 text-3xl font-semibold text-left">Hi {invoice.client_name},</div>
            <div class="my-2 text-xl leading-7">Thanks for using Timary.
            This is an invoice for {invoice.user.first_name}'s services.</div>
            """
            self.assertInHTML(msg, html_message)

        with self.subTest("Testing amount due"):
            msg = "<strong>Amount Due: $155</strong>"
            self.assertInHTML(msg, html_message)

        with self.subTest("Testing one day details"):
            formatted_date = hours_1.date_tracked.strftime("%b %-d")
            msg = f"""
            <div>1 hours on { formatted_date }</div>
            <div>$25</div>
            """
            self.assertInHTML(msg, html_message)

    def test_invoice_preview_context(self):
        user = UserFactory()
        invoice = InvoiceFactory(
            user=user,
            invoice_rate=25,
            next_date=datetime.date.today() - datetime.timedelta(days=1),
        )
        # Save last date before it's updated in send_invoice method to test email contents below
        hours_1 = HoursLineItemFactory(invoice=invoice, quantity=1)
        HoursLineItemFactory(invoice=invoice, quantity=2)
        HoursLineItemFactory(invoice=invoice, quantity=3)

        send_invoice_preview(invoice.id)
        invoice.refresh_from_db()

        email = mail.outbox[0].message().as_string()
        self.assertIn(
            "Pssst! Here is a sneak peek of the invoice going out tomorrow.", email
        )
        html_message = TestSendInvoice.extract_html()

        with self.subTest("Testing title"):
            msg = f"""
            <div class="mt-0 mb-4 text-3xl font-semibold text-left">Hi {invoice.client_name},</div>
            <div class="my-2 text-xl leading-7">Thanks for using Timary.
            This is an invoice for {invoice.user.first_name}'s services.</div>
            """
            self.assertInHTML(msg, html_message)

        with self.subTest("Testing amount due"):
            msg = "<strong>Amount Due: $150</strong>"
            self.assertInHTML(msg, html_message)

        with self.subTest("Testing one day details"):
            formatted_date = hours_1.date_tracked.strftime("%b %-d")
            msg = f"""
            <div>1 hours on { formatted_date }</div>
            <div>$25</div>
            """
            self.assertInHTML(msg, html_message)

    def test_invoice_cannot_accept_payments_without_stripe_enabled(self):
        invoice = InvoiceFactory(user__stripe_payouts_enabled=False)
        HoursLineItemFactory(invoice=invoice)
        send_invoice(invoice.id)

        sent_invoice = SentInvoice.objects.filter(invoice__id=invoice.id).first()

        button_missing = f"""
        <a href="{ settings.SITE_URL }{reverse("timary:pay_invoice", kwargs={"sent_invoice_id": sent_invoice.id})}"
        class="f-fallback button button--green">Pay Invoice</a>
        """
        html_message = TestSendInvoice.extract_html()
        with self.assertRaises(AssertionError):
            self.assertInHTML(button_missing, html_message)

    def test_invoice_can_accept_payments_if_stripe_enabled(self):
        invoice = InvoiceFactory(user__stripe_payouts_enabled=True)
        HoursLineItemFactory(invoice=invoice)
        send_invoice(invoice.id)

        sent_invoice = SentInvoice.objects.filter(invoice__id=invoice.id).first()

        button_missing = f"""
        <a class="btn btn-lg btn-success"
            href="{ settings.SITE_URL }{reverse("timary:pay_invoice", kwargs={"sent_invoice_id": sent_invoice.id})}">
            Pay Invoice
        </a>
        """
        html_message = TestSendInvoice.extract_html()
        self.assertInHTML(button_missing, html_message)

    def test_weekly_invoice_context(self):
        invoice = InvoiceFactory(
            invoice_type=3,
            invoice_rate=1200,
        )
        HoursLineItemFactory(invoice=invoice)
        send_invoice(invoice.id)

        sent_invoice = SentInvoice.objects.filter(invoice__id=invoice.id).first()

        weekly_log_item = f"""
        <div class="flex justify-between py-3 text-xl">
            <div>Week of { template_date(sent_invoice.date_sent, "M j, Y") }</div>
            <div>$1200</div>
        </div>
        """
        html_message = TestSendInvoice.extract_html()
        self.assertInHTML(weekly_log_item, html_message)

    @patch("timary.services.twilio_service.TwilioClient.sent_payment_success")
    def test_paid_invoice_receipt(self, twilio_mock):
        twilio_mock.return_value = None
        invoice = InvoiceFactory(
            user__stripe_payouts_enabled=True, user__first_name="Bob"
        )
        # Save last date before it's updated in send_invoice method to test email contents below
        hours = HoursLineItemFactory(invoice=invoice, quantity=1)
        sent_invoice = SentInvoiceFactory(
            invoice=invoice, paid_status=SentInvoice.PaidStatus.PAID, user=invoice.user
        )
        hours.sent_invoice_id = sent_invoice.id
        hours.save()

        sent_invoice.success_notification()

        html_message = TestSendInvoice.extract_html()
        with self.subTest("Testing title"):
            msg = f"""
            <div class="mt-0 mb-4 text-3xl font-semibold text-left">Hi {invoice.client_name},</div>
            <div class="my-2 text-xl leading-7">Thanks for using Timary.
            This is a copy of the invoice paid for Bob's services on {template_date(sent_invoice.date_sent)}.
            </div>
            """
            self.assertInHTML(msg, html_message)

        with self.subTest("Testing amount due"):
            msg = f"<strong>Total Paid: ${floatformat(sent_invoice.total_price + 5, -2)}</strong>"
            self.assertInHTML(msg, html_message)

    def test_dont_send_invoice_if_no_active_subscription(self):
        hours = HoursLineItemFactory()
        hours.invoice.user.stripe_subscription_status = 3
        hours.invoice.user.save()

        send_invoice(hours.invoice.id)
        self.assertEqual(len(mail.outbox), 0)

        hours.invoice.refresh_from_db()
        self.assertEquals(SentInvoice.objects.count(), 0)


class TestWeeklyInvoiceUpdates(TestCase):
    def setUp(self) -> None:
        self.todays_date = date.today()
        self.current_month = date.strftime(self.todays_date, "%m/%Y")

    @classmethod
    def extract_html(cls):
        s = mail.outbox[0].message().as_string()
        start = s.find("<body>") + len("<body>")
        end = s.find("</body>")
        message = s[start:end]
        return message

    def test_dont_send_weekly_update_if_no_active_subscription(self):
        invoice = InvoiceFactory()
        invoice.user.stripe_subscription_status = 3
        invoice.user.save()
        HoursLineItemFactory(invoice=invoice)

        send_weekly_updates()

        self.assertEquals(len(mail.outbox), 0)

    def test_send_weekly_update(self):
        """Only shows hours tracked for current week, not prior and send email update."""
        invoice = InvoiceFactory(
            last_date=(self.todays_date - datetime.timedelta(days=3)), invoice_type=1
        )
        hour = HoursLineItemFactory(invoice=invoice)
        HoursLineItemFactory(
            invoice=invoice,
            date_tracked=(self.todays_date - datetime.timedelta(days=8)),
        )

        send_weekly_updates()

        self.assertEquals(len(mail.outbox), 1)
        self.assertEquals(
            mail.outbox[0].subject,
            f"Here is a weekly progress update for {invoice.title}",
        )

        html_message = TestWeeklyInvoiceUpdates.extract_html()

        with self.subTest("Testing hours line item"):
            msg = f"""
                <div>{ floatformat(hour.quantity, -2) }  hours on { template_date(hour.date_tracked, "M j")}</div>
                <div>${ floatformat(hour.quantity * invoice.invoice_rate, -2) }</div>
                """
            self.assertInHTML(msg, html_message)
