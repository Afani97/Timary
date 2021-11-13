import datetime

from dateutil.relativedelta import relativedelta
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils.text import slugify

from timary.models import DailyHoursInput, Invoice
from timary.tests.factories import InvoiceFactory, UserProfilesFactory


class TestDailyHours(TestCase):
    def test_create_daily_hours(self):
        invoice = InvoiceFactory()
        hours = DailyHoursInput.objects.create(
            invoice=invoice, hours=1, date_tracked=datetime.date.today()
        )
        self.assertIsNotNone(hours)
        self.assertEqual(hours.hours, 1)
        self.assertEqual(hours.invoice, invoice)
        self.assertEqual(hours.date_tracked, datetime.date.today())
        self.assertEqual(
            hours.slug_id, f"{slugify(invoice.title)}-{str(hours.id.int)[:6]}"
        )

    def test_error_creating_hours_less_than_0(self):
        invoice = InvoiceFactory()
        with self.assertRaises(ValidationError):
            DailyHoursInput.objects.create(
                invoice=invoice, hours=-1, date_tracked=datetime.date.today()
            )

    def test_error_creating_hours_greater_than_24(self):
        invoice = InvoiceFactory()
        with self.assertRaises(ValidationError):
            DailyHoursInput.objects.create(
                invoice=invoice, hours=24, date_tracked=datetime.date.today()
            )

    def test_error_creating_hours_with_3_decimal_places(self):
        invoice = InvoiceFactory()
        with self.assertRaises(ValidationError):
            DailyHoursInput.objects.create(
                invoice=invoice, hours=2.556, date_tracked=datetime.date.today()
            )

    def test_error_creating_without_invoice(self):
        with self.assertRaises(ValidationError):
            DailyHoursInput.objects.create(hours=1, date_tracked=datetime.date.today())


class TestInvoice(TestCase):
    def test_invoice(self):
        profile = UserProfilesFactory()
        next_date = datetime.date.today() + datetime.timedelta(weeks=1)
        invoice = Invoice.objects.create(
            title="Some title",
            user=profile,
            hourly_rate=100,
            email_recipient_name="User",
            email_recipient="user@test.com",
            invoice_interval="W",
            next_date=next_date,
            last_date=datetime.date.today(),
        )
        self.assertIsNotNone(invoice)
        self.assertIsNotNone(invoice.email_id)
        self.assertEqual(invoice.title, "Some title")
        self.assertEqual(invoice.user, profile)
        self.assertEqual(invoice.hourly_rate, 100)
        self.assertEqual(invoice.email_recipient_name, "User")
        self.assertEqual(invoice.email_recipient, "user@test.com")
        self.assertEqual(invoice.next_date, next_date)
        self.assertEqual(invoice.last_date, datetime.date.today())
        self.assertEqual(invoice.slug_title, slugify(invoice.title))

    def test_error_creating_invoice_rate_less_than_1(self):
        profile = UserProfilesFactory()
        with self.assertRaises(ValidationError):
            Invoice.objects.create(
                title="Some title",
                user=profile,
                hourly_rate=-10,
                email_recipient_name="User",
                email_recipient="user@test.com",
            )

    def test_error_creating_invoice_without_user_profile(self):
        with self.assertRaises(ValidationError):
            Invoice.objects.create(
                title="Some title",
                hourly_rate=-10,
                email_recipient_name="User",
                email_recipient="user@test.com",
            )

    def test_error_creating_invoice_without_email_recipient_name(self):
        profile = UserProfilesFactory()
        with self.assertRaises(ValidationError):
            Invoice.objects.create(
                title="Some title",
                user=profile,
                hourly_rate=-10,
                email_recipient="user@test.com",
            )

    def test_error_creating_invoice_without_email_recipient(self):
        profile = UserProfilesFactory()
        with self.assertRaises(ValidationError):
            Invoice.objects.create(
                title="Some title",
                user=profile,
                hourly_rate=-10,
                email_recipient_name="User",
            )

    def test_invoice_calculate_next_date(self):
        today = datetime.date.today()
        invoice = InvoiceFactory(invoice_interval="D")
        invoice.calculate_next_date()
        self.assertEqual(invoice.next_date, today + datetime.timedelta(days=1))

        invoice.invoice_interval = "W"
        invoice.calculate_next_date()
        self.assertEqual(invoice.next_date, today + datetime.timedelta(weeks=1))

        invoice.invoice_interval = "B"
        invoice.calculate_next_date()
        self.assertEqual(invoice.next_date, today + datetime.timedelta(weeks=2))

        invoice.invoice_interval = "M"
        invoice.calculate_next_date()
        self.assertEqual(invoice.next_date, today + relativedelta(months=1))

        invoice.invoice_interval = "Q"
        invoice.calculate_next_date()
        self.assertEqual(invoice.next_date, today + relativedelta(months=3))

        invoice.invoice_interval = "Y"
        invoice.calculate_next_date()
        self.assertEqual(invoice.next_date, today + relativedelta(years=1))
        self.assertEqual(invoice.last_date, today)
