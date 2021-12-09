import datetime
from datetime import date
from unittest.mock import patch

from django.core import mail
from django.test import TestCase
from django.utils.timezone import localtime, now

from timary.tasks import gather_invoices, send_invoice
from timary.tests.factories import DailyHoursFactory, InvoiceFactory


class TestGatherInvoices(TestCase):
    @patch("timary.tasks.async_task")
    @patch("django.core.mail.send_mail")
    def test_gather_0_invoices(self, send_email_mock, send_invoice_mock):
        send_email_mock.return_value = None
        send_invoice_mock.return_value = None
        invoices_sent = gather_invoices()
        self.assertEqual("Invoices sent: 0", invoices_sent)

    @patch("timary.tasks.async_task")
    @patch("django.core.mail.send_mail")
    def test_gather_0_invoices_for_today(self, send_email_mock, send_invoice_mock):
        send_email_mock.return_value = None
        send_invoice_mock.return_value = None
        DailyHoursFactory(
            invoice__next_date=datetime.date.today() + datetime.timedelta(days=1)
        )
        DailyHoursFactory(
            invoice__next_date=datetime.date.today() - datetime.timedelta(days=1)
        )
        invoices_sent = gather_invoices()
        self.assertEqual("Invoices sent: 0", invoices_sent)

    @patch("timary.tasks.async_task")
    @patch("django.core.mail.send_mail")
    def test_gather_1_invoice_for_today(self, send_email_mock, send_invoice_mock):
        send_email_mock.return_value = None
        send_invoice_mock.return_value = None
        DailyHoursFactory(
            invoice__next_date=datetime.date.today() + datetime.timedelta(days=1)
        )
        DailyHoursFactory()
        invoices_sent = gather_invoices()
        self.assertEqual("Invoices sent: 1", invoices_sent)

    @patch("timary.tasks.async_task")
    @patch("django.core.mail.send_mail")
    def test_gather_3_invoices_for_today(self, send_email_mock, send_invoice_mock):
        send_email_mock.return_value = None
        send_invoice_mock.return_value = None
        DailyHoursFactory()
        DailyHoursFactory()
        DailyHoursFactory()
        invoices_sent = gather_invoices()
        self.assertEqual("Invoices sent: 3", invoices_sent)


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
            ).strftime("%b. %-d, %Y")
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
            <td width="80%" class="purchase_item"><span class="f-fallback">1.0 hours on { formatted_date }</span></td>
            <td class="align-right" width="20%" class="purchase_item"><span class="f-fallback">$25</span></td>
            """
            self.assertInHTML(msg, html_message)
