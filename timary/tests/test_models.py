import datetime

from dateutil.relativedelta import relativedelta
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils.text import slugify

from timary.models import DailyHoursInput, Invoice, User
from timary.tests.factories import DailyHoursFactory, InvoiceFactory, UserFactory


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
        user = UserFactory()
        next_date = datetime.date.today() + datetime.timedelta(weeks=1)
        invoice = Invoice.objects.create(
            title="Some title",
            user=user,
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
        self.assertEqual(invoice.user, user)
        self.assertEqual(invoice.hourly_rate, 100)
        self.assertEqual(invoice.email_recipient_name, "User")
        self.assertEqual(invoice.email_recipient, "user@test.com")
        self.assertEqual(invoice.next_date, next_date)
        self.assertEqual(invoice.last_date, datetime.date.today())
        self.assertEqual(invoice.slug_title, slugify(invoice.title))

    def test_error_creating_invoice_rate_less_than_1(self):
        user = UserFactory()
        with self.assertRaises(ValidationError):
            Invoice.objects.create(
                title="Some title",
                user=user,
                hourly_rate=-10,
                email_recipient_name="User",
                email_recipient="user@test.com",
            )

    def test_error_creating_invoice_without_user(self):
        with self.assertRaises(ValidationError):
            Invoice.objects.create(
                title="Some title",
                hourly_rate=-10,
                email_recipient_name="User",
                email_recipient="user@test.com",
            )

    def test_error_creating_invoice_without_email_recipient_name(self):
        user = UserFactory()
        with self.assertRaises(ValidationError):
            Invoice.objects.create(
                title="Some title",
                user=user,
                hourly_rate=-10,
                email_recipient="user@test.com",
            )

    def test_error_creating_invoice_without_email_recipient(self):
        user = UserFactory()
        with self.assertRaises(ValidationError):
            Invoice.objects.create(
                title="Some title",
                user=user,
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

    def test_get_hours_stats(self):
        two_days_ago = datetime.date.today() - datetime.timedelta(days=2)
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        invoice = InvoiceFactory(hourly_rate=50, last_date=two_days_ago)
        hours1 = DailyHoursFactory(invoice=invoice, date_tracked=yesterday)
        hours2 = DailyHoursFactory(invoice=invoice)
        hours_list = sorted([hours1, hours2], key=lambda x: x.date_tracked)

        hours_tracked, total_hours = invoice.get_hours_stats()
        self.assertListEqual(list(hours_tracked), hours_list)
        self.assertEqual(
            total_hours, (hours1.hours + hours2.hours) * invoice.hourly_rate
        )

    def test_get_hours_stats_with_date_range(self):
        two_days_ago = datetime.date.today() - datetime.timedelta(days=2)
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        invoice = InvoiceFactory(hourly_rate=50, last_date=yesterday)
        DailyHoursFactory(invoice=invoice, date_tracked=two_days_ago)
        hours2 = DailyHoursFactory(invoice=invoice)

        hours_tracked, total_hours = invoice.get_hours_stats(
            (yesterday, datetime.date.today())
        )
        self.assertListEqual(list(hours_tracked), [hours2])
        self.assertEqual(total_hours, hours2.hours * invoice.hourly_rate)


class TestUser(TestCase):
    def test_user(self):
        user = User.objects.create(
            first_name="Ari",
            last_name="Fani",
            username="test@test.com",
            email="test@test.com",
            phone_number="+17742613186",
            phone_number_availability=["Mon", "Tue", "Wed"],
        )
        self.assertIsNotNone(user)
        self.assertEqual(user.first_name, "Ari")
        self.assertEqual(user.last_name, "Fani")
        self.assertEqual(user.username, "test@test.com")
        self.assertEqual(user.email, "test@test.com")
        self.assertEqual(user.phone_number, "+17742613186")
        self.assertEqual(user.membership_tier, User.MembershipTier.STARTER)
        self.assertListEqual(user.phone_number_availability, ["Mon", "Tue", "Wed"])

    def test_settings_dict(self):
        user = UserFactory(phone_number_availability=["Mon", "Tue"])
        self.assertEqual(
            user.settings,
            {
                "phone_number_availability": ["Mon", "Tue"],
                "quickbooks_connected": False,
            },
        )

    def test_get_remaining_invoices(self):
        user = UserFactory()
        InvoiceFactory(user=user)
        InvoiceFactory(user=user)
        self.assertEqual(len(user.invoices_not_logged), 2)

    def test_get_1_remaining_invoices(self):
        user = UserFactory()
        InvoiceFactory(user=user)
        InvoiceFactory()
        self.assertEqual(len(user.invoices_not_logged), 1)

    def test_get_2_remaining_invoices(self):
        user = UserFactory()
        DailyHoursFactory(invoice__user=user)
        InvoiceFactory(user=user)
        InvoiceFactory(user=user)
        self.assertEqual(len(user.invoices_not_logged), 2)

    def test_get_1_remaining_invoices_logged_yesterday(self):
        user = UserFactory()
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        DailyHoursFactory(invoice__user=user, date_tracked=yesterday)
        InvoiceFactory(user=user)
        self.assertEqual(len(user.invoices_not_logged), 2)

    def test_get_1_remaining_invoices_logged_today(self):
        user = UserFactory()
        DailyHoursFactory(invoice__user=user, date_tracked=datetime.date.today())
        InvoiceFactory(user=user)
        self.assertEqual(len(user.invoices_not_logged), 1)

    def test_can_accept_payments(self):
        with self.subTest("Payouts enabled"):
            user = UserFactory(stripe_payouts_enabled=True)
            self.assertTrue(user.can_accept_payments)

        with self.subTest("Payouts not enabled"):
            user = UserFactory(stripe_payouts_enabled=False)
            self.assertFalse(user.can_accept_payments)

    def test_can_receive_texts(self):
        with self.subTest("Starter tier"):
            user = UserFactory(membership_tier=User.MembershipTier.STARTER)
            self.assertFalse(user.can_receive_texts)

        with self.subTest("Professional tier"):
            user = UserFactory(membership_tier=User.MembershipTier.PROFESSIONAL)
            self.assertTrue(user.can_receive_texts)

        with self.subTest("Business tier"):
            user = UserFactory(membership_tier=User.MembershipTier.BUSINESS)
            self.assertTrue(user.can_receive_texts)

    def test_can_create_invoices(self):
        with self.subTest("Zero invoices"):
            user = UserFactory()
            self.assertFalse(user.can_create_invoices)

        with self.subTest("Starter tier, only one allowed"):
            user = UserFactory(membership_tier=User.MembershipTier.STARTER)
            InvoiceFactory(user=user)
            self.assertFalse(user.can_create_invoices)

        with self.subTest("Professional tier, limit not reached"):
            user = UserFactory(membership_tier=User.MembershipTier.PROFESSIONAL)
            InvoiceFactory(user=user)
            self.assertTrue(user.can_create_invoices)

        with self.subTest("Business tier, limit reached"):
            user = UserFactory(membership_tier=User.MembershipTier.PROFESSIONAL)
            InvoiceFactory(user=user)
            InvoiceFactory(user=user)
            self.assertFalse(user.can_create_invoices)

        with self.subTest("Business tier, limit reached"):
            user = UserFactory(membership_tier=User.MembershipTier.BUSINESS)
            InvoiceFactory(user=user)
            self.assertTrue(user.can_create_invoices)
