import zoneinfo
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from timary.querysets import HourStats
from timary.tests.factories import (
    HoursLineItemFactory,
    IntervalInvoiceFactory,
    SentInvoiceFactory,
    UserFactory,
    WeeklyInvoiceFactory,
)


class TestHourStats(TestCase):
    @patch("timary.querysets.timezone")
    def test_hour_stats_current_month(self, date_mock):
        date_mock.now.return_value = timezone.datetime(
            2022, 8, 25, tzinfo=zoneinfo.ZoneInfo("America/New_York")
        )
        user = UserFactory()
        invoice = IntervalInvoiceFactory(user=user, rate=50)
        sent_invoice = SentInvoiceFactory(
            invoice=invoice,
            user=user,
            total_price=300,
            paid_status=2,
            date_sent=timezone.datetime(
                2022, 8, 25, tzinfo=zoneinfo.ZoneInfo("America/New_York")
            ),
        )
        sent_invoice.user = user
        sent_invoice.save()
        HoursLineItemFactory(
            invoice=invoice,
            date_tracked=timezone.datetime(
                2022, 8, 25, tzinfo=zoneinfo.ZoneInfo("America/New_York")
            ),
            quantity=2,
        )

        HoursLineItemFactory(
            invoice=invoice,
            date_tracked=timezone.datetime(
                2022, 8, 25, tzinfo=zoneinfo.ZoneInfo("America/New_York")
            ),
            sent_invoice_id=sent_invoice.id,
            quantity=3,
        )

        weekly_invoice = WeeklyInvoiceFactory(user=user, rate=1500)
        SentInvoiceFactory(
            invoice=weekly_invoice,
            user=user,
            total_price=weekly_invoice.rate,
            date_sent=timezone.datetime(
                2022, 8, 25, tzinfo=zoneinfo.ZoneInfo("America/New_York")
            ),
        )

        hour_stats = HourStats(user=user)

        current_month_stats = hour_stats.get_current_month_stats()
        self.assertEqual(float(current_month_stats["total_hours"]), 5)
        self.assertEqual(float(current_month_stats["total_amount"]), 1900)

    @patch("timary.querysets.timezone")
    def test_hour_stats_current_month_do_not_include_weekly_invoice_hours_without_sent_invoice(
        self, date_mock
    ):
        # Don't calculate hours for weekly invoices, only their sent invoices
        date_mock.now.return_value = timezone.datetime(
            2022, 8, 25, tzinfo=zoneinfo.ZoneInfo("America/New_York")
        )
        user = UserFactory()
        invoice = WeeklyInvoiceFactory(user=user, rate=1500)
        sent_invoice = SentInvoiceFactory(
            invoice=invoice,
            user=user,
            total_price=1500,
            paid_status=2,
            date_sent=timezone.datetime(
                2022, 8, 25, tzinfo=zoneinfo.ZoneInfo("America/New_York")
            ),
        )
        sent_invoice.user = user
        sent_invoice.save()
        HoursLineItemFactory(
            invoice=invoice,
            date_tracked=timezone.datetime(
                2022, 8, 25, tzinfo=zoneinfo.ZoneInfo("America/New_York")
            ),
            quantity=2,
        )

        HoursLineItemFactory(
            invoice=invoice,
            date_tracked=timezone.datetime(
                2022, 8, 25, tzinfo=zoneinfo.ZoneInfo("America/New_York")
            ),
            sent_invoice_id=sent_invoice.id,
            quantity=3,
        )

        hour_stats = HourStats(user=user)

        current_month_stats = hour_stats.get_current_month_stats()
        self.assertEqual(float(current_month_stats["total_hours"]), 5)
        self.assertEqual(float(current_month_stats["total_amount"]), 1500)

    @patch("timary.querysets.get_last_month")
    @patch("timary.querysets.timezone")
    def test_hour_stats_last_month(self, date_mock, last_month_mock):
        date_mock.now.return_value = timezone.datetime(
            2022, 8, 25, tzinfo=zoneinfo.ZoneInfo("America/New_York")
        )
        last_month_mock.return_value = timezone.datetime(
            2022, 7, 1, tzinfo=zoneinfo.ZoneInfo("America/New_York")
        )
        user = UserFactory()
        invoice = IntervalInvoiceFactory(user=user, rate=50)
        sent_invoice = SentInvoiceFactory(
            invoice=invoice,
            user=user,
            date_sent=timezone.datetime(
                2022, 7, 25, tzinfo=zoneinfo.ZoneInfo("America/New_York")
            ),
            total_price=300,
        )
        HoursLineItemFactory(
            invoice=invoice,
            quantity=2,
            date_tracked=timezone.datetime(
                2022, 7, 25, tzinfo=zoneinfo.ZoneInfo("America/New_York")
            ),
        )

        HoursLineItemFactory(
            invoice=invoice,
            sent_invoice_id=sent_invoice.id,
            quantity=3,
            date_tracked=timezone.datetime(
                2022, 7, 25, tzinfo=zoneinfo.ZoneInfo("America/New_York")
            ),
        )

        hour_stats = HourStats(user=user)

        last_month_stats = hour_stats.get_last_month_stats()
        self.assertEqual(float(last_month_stats["total_hours"]), 5)
        self.assertEqual(float(last_month_stats["total_amount"]), 400)
