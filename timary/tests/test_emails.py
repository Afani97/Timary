import datetime
from datetime import date
from unittest.mock import patch

from django.conf import settings
from django.core import mail
from django.template.defaultfilters import date as template_date
from django.template.defaultfilters import floatformat
from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import localtime, now

from timary.models import SentInvoice
from timary.tasks import (
    gather_invoices,
    send_invoice,
    send_invoice_preview,
    send_weekly_updates,
)
from timary.tests.factories import DailyHoursFactory, InvoiceFactory


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
        DailyHoursFactory(
            invoice__next_date=datetime.date.today() + datetime.timedelta(days=2)
        )
        DailyHoursFactory(
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
        DailyHoursFactory(invoice__next_date=None)
        DailyHoursFactory()
        invoices_sent = gather_invoices()
        self.assertEqual("Invoices sent: 1", invoices_sent)
        self.assertEquals(
            mail.outbox[0].subject,
            "Sent out 1 invoices",
        )

    @patch("timary.tasks.async_task")
    def test_gather_1_invoice_for_today(self, send_invoice_mock):
        send_invoice_mock.return_value = None
        DailyHoursFactory(
            invoice__next_date=datetime.date.today() + datetime.timedelta(days=2)
        )
        DailyHoursFactory()
        invoices_sent = gather_invoices()
        self.assertEqual("Invoices sent: 1", invoices_sent)
        self.assertEquals(
            mail.outbox[0].subject,
            "Sent out 1 invoices",
        )

    @patch("timary.tasks.async_task")
    def test_gather_3_invoices_for_today(self, send_invoice_mock):
        send_invoice_mock.return_value = None
        DailyHoursFactory()
        DailyHoursFactory()
        DailyHoursFactory()
        invoices_sent = gather_invoices()
        self.assertEqual("Invoices sent: 3", invoices_sent)
        self.assertEquals(
            mail.outbox[0].subject,
            "Sent out 3 invoices",
        )

    @patch("timary.tasks.async_task")
    def test_gather_1_invoice_preview_for_tomorrow(self, send_invoice_mock):
        send_invoice_mock.return_value = None
        DailyHoursFactory(
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
        DailyHoursFactory(
            invoice__next_date=datetime.date.today() + datetime.timedelta(days=1)
        )
        DailyHoursFactory(
            invoice__next_date=datetime.date.today() + datetime.timedelta(days=1)
        )
        DailyHoursFactory(
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
        DailyHoursFactory()
        DailyHoursFactory(
            invoice__next_date=datetime.date.today() + datetime.timedelta(days=1)
        )
        DailyHoursFactory(
            invoice__next_date=datetime.date.today() + datetime.timedelta(days=2)
        )
        invoices_sent = gather_invoices()
        self.assertEqual("Invoices sent: 2", invoices_sent)
        self.assertEquals(
            mail.outbox[0].subject,
            "Sent out 2 invoices",
        )


class TestSendInvoice(TestCase):
    def setUp(self) -> None:
        self.todays_date = localtime(now()).date()
        self.current_month = date.strftime(self.todays_date, "%m/%Y")

    @classmethod
    def extract_html(cls):
        s = mail.outbox[0].message().as_string()
        start = s.find("<body>") + len("<body>")
        end = s.find("</body>")
        message = s[start:end]
        return message

    def test_send_one_invoice(self):
        hours = DailyHoursFactory()
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
        h1 = DailyHoursFactory(date_tracked=two_days_ago, invoice=invoice)
        h2 = DailyHoursFactory(date_tracked=yesterday, invoice=invoice)
        h3 = DailyHoursFactory(date_tracked=self.todays_date, invoice=invoice)

        send_invoice(invoice.id)
        self.assertEquals(len(mail.outbox), 1)
        self.assertEquals(SentInvoice.objects.count(), 1)

        sent_invoice = SentInvoice.objects.first()
        self.assertEquals(sent_invoice.hours_start_date, two_days_ago)
        self.assertEquals(sent_invoice.hours_end_date, self.todays_date)
        self.assertEquals(
            sent_invoice.total_price,
            (h1.hours + h2.hours + h3.hours) * invoice.hourly_rate,
        )

    def test_sent_invoices_only_2_hours(self):
        yesterday = self.todays_date - datetime.timedelta(days=1)
        invoice = InvoiceFactory(
            last_date=self.todays_date - datetime.timedelta(days=1)
        )
        DailyHoursFactory(
            date_tracked=self.todays_date - datetime.timedelta(days=2), invoice=invoice
        )
        h2 = DailyHoursFactory(date_tracked=yesterday, invoice=invoice)
        h3 = DailyHoursFactory(date_tracked=self.todays_date, invoice=invoice)

        send_invoice(invoice.id)
        self.assertEquals(len(mail.outbox), 1)
        self.assertEquals(SentInvoice.objects.count(), 1)

        sent_invoice = SentInvoice.objects.first()
        self.assertEquals(sent_invoice.hours_start_date, yesterday)
        self.assertEquals(sent_invoice.hours_end_date, self.todays_date)
        self.assertEquals(
            sent_invoice.total_price,
            (h2.hours + h3.hours) * invoice.hourly_rate,
        )

    def test_dont_send_invoice_if_no_tracked_hours(self):
        hours = DailyHoursFactory(
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

    def test_send_two_invoice_and_subjects(self):
        hours1 = DailyHoursFactory()
        hours2 = DailyHoursFactory()
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
        invoice = InvoiceFactory(hourly_rate=25)
        # Save last date before it's updated in send_invoice method to test email contents below
        hours_1 = DailyHoursFactory(invoice=invoice, hours=1)
        DailyHoursFactory(invoice=invoice, hours=2)
        DailyHoursFactory(invoice=invoice, hours=3)

        send_invoice(invoice.id)
        invoice.refresh_from_db()

        html_message = TestSendInvoice.extract_html()

        with self.subTest("Testing header"):
            next_weeks_date = (
                localtime(now()).date() + datetime.timedelta(weeks=1)
            ).strftime("%B %-d, %Y")
            msg = (
                f'<span class="preheader">This is an invoice for '
                f"{invoice.user.first_name}'s services. "
                f"Please submit payment by {next_weeks_date}</span>"
            )
            self.assertInHTML(msg, html_message)

        with self.subTest("Testing title"):
            msg = f"""
            <h1>Hi {invoice.email_recipient_name},</h1>
            <p>Thanks for using Timary. This is an invoice for {invoice.user.first_name}'s services.</p>
            """
            self.assertInHTML(msg, html_message)

        with self.subTest("Testing amount due"):
            msg = "<strong>Amount Due: $160</strong>"
            self.assertInHTML(msg, html_message)

        with self.subTest("Testing one day details"):
            formatted_date = hours_1.date_tracked.strftime("%b %-d")
            msg = f"""
            <td width="80%" class="purchase_item"><span class="f-fallback">1.00 hours on { formatted_date }</span></td>
            <td class="align-right" width="20%" class="purchase_item"><span class="f-fallback">$25</span></td>
            """
            self.assertInHTML(msg, html_message)

    def test_invoice_preview_context(self):
        invoice = InvoiceFactory(
            hourly_rate=25, next_date=datetime.date.today() - datetime.timedelta(days=1)
        )
        # Save last date before it's updated in send_invoice method to test email contents below
        hours_1 = DailyHoursFactory(invoice=invoice, hours=1)
        DailyHoursFactory(invoice=invoice, hours=2)
        DailyHoursFactory(invoice=invoice, hours=3)

        send_invoice_preview(invoice.id)
        invoice.refresh_from_db()

        email = mail.outbox[0].message().as_string()
        self.assertIn(
            "Pssst! Here is a sneak peek of the invoice going out tomorrow.", email
        )
        html_message = TestSendInvoice.extract_html()

        with self.subTest("Testing header"):
            next_weeks_date = (
                localtime(now()).date() + datetime.timedelta(weeks=1)
            ).strftime("%B %-d, %Y")
            msg = (
                f'<span class="preheader">This is an invoice for '
                f"{invoice.user.first_name}'s services. "
                f"Please submit payment by {next_weeks_date}</span>"
            )
            self.assertInHTML(msg, html_message)

        with self.subTest("Testing title"):
            msg = f"""
            <h1>Hi {invoice.email_recipient_name},</h1>
            <p>Thanks for using Timary. This is an invoice for {invoice.user.first_name}'s services.</p>
            """
            self.assertInHTML(msg, html_message)

        with self.subTest("Testing amount due"):
            msg = "<strong>Amount Due: $150</strong>"
            self.assertInHTML(msg, html_message)

        with self.subTest("Testing one day details"):
            formatted_date = hours_1.date_tracked.strftime("%b %-d")
            msg = f"""
            <td width="80%" class="purchase_item"><span class="f-fallback">1.00 hours on { formatted_date }</span></td>
            <td class="align-right" width="20%" class="purchase_item"><span class="f-fallback">$25</span></td>
            """
            self.assertInHTML(msg, html_message)

    def test_invoice_cannot_accept_payments_without_stripe_enabled(self):
        invoice = InvoiceFactory(user__stripe_payouts_enabled=False)
        DailyHoursFactory(invoice=invoice)
        send_invoice(invoice.id)

        sent_invoice = SentInvoice.objects.filter(invoice__id=invoice.id).first()

        button_missing = f"""
        <a href="{ settings.SITE_URL }{reverse("timary:pay_invoice", kwargs={"sent_invoice_id": sent_invoice.id})}"
        class="f-fallback button button--green">Pay Invoice</a>
        """
        html_message = TestSendInvoice.extract_html()
        with self.assertRaises(AssertionError):
            self.assertInHTML(button_missing, html_message)

    def test_invoice_cannot_accept_payments_is_starter(self):
        invoice = InvoiceFactory(
            user__stripe_payouts_enabled=True, user__membership_tier=5
        )
        DailyHoursFactory(invoice=invoice)
        send_invoice(invoice.id)

        sent_invoice = SentInvoice.objects.filter(invoice__id=invoice.id).first()

        button_missing = f"""
        <a href="{ settings.SITE_URL }{reverse("timary:pay_invoice", kwargs={"sent_invoice_id": sent_invoice.id})}"
        class="f-fallback button button--green">Pay Invoice</a>
        """
        html_message = TestSendInvoice.extract_html()
        with self.assertRaises(AssertionError):
            self.assertInHTML(button_missing, html_message)

    def test_invoice_can_accept_payments_if_stripe_enabled_and_is_professional(self):
        invoice = InvoiceFactory(user__stripe_payouts_enabled=True)
        DailyHoursFactory(invoice=invoice)
        send_invoice(invoice.id)

        sent_invoice = SentInvoice.objects.filter(invoice__id=invoice.id).first()

        button_missing = f"""
        <a href="{ settings.SITE_URL }{reverse("timary:pay_invoice", kwargs={"sent_invoice_id": sent_invoice.id})}"
        class="f-fallback button button--green">Pay Invoice</a>
        """
        html_message = TestSendInvoice.extract_html()
        self.assertInHTML(button_missing, html_message)

    def test_invoice_can_accept_payments_if_stripe_enabled_and_is_business(self):
        invoice = InvoiceFactory(
            user__stripe_payouts_enabled=True, user__membership_tier=49
        )
        DailyHoursFactory(invoice=invoice)
        send_invoice(invoice.id)

        sent_invoice = SentInvoice.objects.filter(invoice__id=invoice.id).first()

        button_missing = f"""
        <a href="{ settings.SITE_URL }{reverse("timary:pay_invoice", kwargs={"sent_invoice_id": sent_invoice.id})}"
        class="f-fallback button button--green">Pay Invoice</a>
        """
        html_message = TestSendInvoice.extract_html()
        self.assertInHTML(button_missing, html_message)


class TestWeeklyInvoiceUpdates(TestCase):
    def setUp(self) -> None:
        self.todays_date = localtime(now()).date()
        self.current_month = date.strftime(self.todays_date, "%m/%Y")

    @classmethod
    def extract_html(cls):
        s = mail.outbox[0].message().as_string()
        start = s.find("<body>") + len("<body>")
        end = s.find("</body>")
        message = s[start:end]
        return message

    def test_send_weekly_update(self):
        """Only shows hours tracked for current week, not prior and send email update."""
        invoice = InvoiceFactory(
            last_date=(self.todays_date - datetime.timedelta(days=3))
        )
        hour = DailyHoursFactory(invoice=invoice)
        DailyHoursFactory(
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
                <tr>
                    <td width="80%" class="purchase_item">
                        <span class="f-fallback">
                            { floatformat(hour.hours, 2) }  hours on { template_date(hour.date_tracked, "M j")}
                        </span>
                    </td>
                    <td class="align-right" width="20%" class="purchase_item">
                        <span class="f-fallback">${ floatformat(hour.hours * invoice.hourly_rate) }</span>
                    </td>
                </tr>
                """
            self.assertInHTML(msg, html_message)

        with self.subTest("Testing invoice budget"):
            msg = f"""
                <div
                    class="radial-progress text-black bg-accent  border-4 border-accent"
                    style="--value:{ invoice.budget_percentage }; --thickness: 4px;"
                >
                    { floatformat(invoice.budget_percentage,-2) }%
                </div>
                """
            self.assertInHTML(msg, html_message)
