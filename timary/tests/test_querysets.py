import datetime
from unittest.mock import patch

from django.test import TestCase

from timary.querysets import HourStats
from timary.tests.factories import (
    DailyHoursFactory,
    InvoiceFactory,
    SentInvoiceFactory,
    UserFactory,
)


class TestHourStats(TestCase):
    @patch("timary.querysets.datetime")
    def test_hour_stats_current_month(self, date_mock):
        date_mock.today.return_value = datetime.date(2022, 8, 25)
        user = UserFactory()
        invoice = InvoiceFactory(user=user, invoice_rate=50, invoice_type=1)
        sent_invoice = SentInvoiceFactory(invoice=invoice, user=user, total_price=300)
        DailyHoursFactory(invoice=invoice, hours=2)

        DailyHoursFactory(invoice=invoice, sent_invoice_id=sent_invoice.id, hours=3)

        hour_stats = HourStats(user=user)

        current_month_stats = hour_stats.get_current_month_stats()
        self.assertEqual(float(current_month_stats["total_hours"]), 5)
        self.assertEqual(float(current_month_stats["total_amount"]), 400)

    @patch("timary.querysets.datetime")
    def test_hour_stats_last_month(self, date_mock):
        date_mock.today.return_value = datetime.date(2022, 8, 25)
        user = UserFactory()
        invoice = InvoiceFactory(user=user, invoice_rate=50, invoice_type=1)
        sent_invoice = SentInvoiceFactory(
            invoice=invoice,
            user=user,
            date_sent=datetime.date(2022, 7, 25),
            total_price=300,
        )
        DailyHoursFactory(
            invoice=invoice, hours=2, date_tracked=datetime.date(2022, 7, 25)
        )

        DailyHoursFactory(
            invoice=invoice,
            sent_invoice_id=sent_invoice.id,
            hours=3,
            date_tracked=datetime.date(2022, 7, 25),
        )

        hour_stats = HourStats(user=user)

        last_month_stats = hour_stats.get_last_month_stats()
        self.assertEqual(float(last_month_stats["total_hours"]), 5)
        self.assertEqual(float(last_month_stats["total_amount"]), 400)

    @patch("timary.querysets.datetime")
    def test_hour_stats_current_year(self, date_mock):
        date_mock.today.return_value = datetime.date(2022, 8, 25)
        user = UserFactory()
        invoice = InvoiceFactory(user=user, invoice_rate=50, invoice_type=1)
        sent_invoice = SentInvoiceFactory(
            invoice=invoice,
            user=user,
            date_sent=datetime.date(2022, 7, 25),
            total_price=300,
        )
        DailyHoursFactory(
            invoice=invoice, hours=2, date_tracked=datetime.date(2022, 5, 25)
        )

        DailyHoursFactory(
            invoice=invoice,
            sent_invoice_id=sent_invoice.id,
            hours=3,
            date_tracked=datetime.date(2022, 4, 25),
        )

        hour_stats = HourStats(user=user)

        this_year_stats = hour_stats.get_this_year_stats()
        self.assertEqual(float(this_year_stats["total_hours"]), 5)
        self.assertEqual(float(this_year_stats["total_amount"]), 400)
