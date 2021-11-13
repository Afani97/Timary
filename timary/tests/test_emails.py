import datetime
from datetime import date
from unittest.mock import patch

from django.core import mail
from django.test import TestCase
from django.utils.timezone import localtime, now

from timary.models import Invoice
from timary.tasks import gather_invoices, send_invoice
from timary.tests.factories import DailyHoursFactory


class TestGatherInvoices(TestCase):
    @patch("timary.tasks.async_task")
    def test_gather_0_invoices(self, send_invoice_mock):
        send_invoice_mock.return_value = None
        invoices_sent = gather_invoices()
        self.assertEqual("Invoices sent: 0", invoices_sent)

    @patch("timary.tasks.async_task")
    def test_gather_0_invoices_for_today(self, send_invoice_mock):
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
    def test_gather_1_invoice_for_today(self, send_invoice_mock):
        send_invoice_mock.return_value = None
        DailyHoursFactory(
            invoice__next_date=datetime.date.today() + datetime.timedelta(days=1)
        )
        DailyHoursFactory()
        invoices_sent = gather_invoices()
        self.assertEqual("Invoices sent: 1", invoices_sent)

    @patch("timary.tasks.async_task")
    def test_gather_3_invoices_for_today(self, send_invoice_mock):
        send_invoice_mock.return_value = None
        DailyHoursFactory()
        DailyHoursFactory()
        DailyHoursFactory()
        invoices_sent = gather_invoices()
        self.assertEqual("Invoices sent: 3", invoices_sent)


class TestSendInvoice(TestCase):
    def setUp(self) -> None:
        DailyHoursFactory()
        self.invoice = Invoice.objects.first()
        self.todays_date = localtime(now()).date()
        self.current_month = date.strftime(self.todays_date, "%m/%Y")

    def test_send_one_invoice(self):
        send_invoice(self.invoice.id)
        self.assertEquals(len(mail.outbox), 1)
        self.assertEquals(
            mail.outbox[0].subject,
            f"{self.invoice.title}'s Invoice from {self.invoice.user.user.first_name} for {self.current_month}",
        )
