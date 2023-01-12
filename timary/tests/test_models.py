import datetime
from decimal import Decimal
from unittest.mock import patch

from dateutil.relativedelta import relativedelta
from django.core.exceptions import ValidationError
from django.template.defaultfilters import date as template_date
from django.template.defaultfilters import floatformat
from django.test import TestCase
from django.utils.text import slugify

from timary.hours_manager import HoursManager
from timary.models import (
    HoursLineItem,
    IntervalInvoice,
    MilestoneInvoice,
    SentInvoice,
    User,
    WeeklyInvoice,
)
from timary.tests.factories import (
    HoursLineItemFactory,
    IntervalInvoiceFactory,
    InvoiceFactory,
    MilestoneInvoiceFactory,
    SentInvoiceFactory,
    UserFactory,
    WeeklyInvoiceFactory,
)
from timary.utils import get_date_parsed, get_starting_week_from_date


class TestDailyHours(TestCase):
    def test_create_daily_hours(self):
        invoice = IntervalInvoiceFactory()
        hours = HoursLineItem.objects.create(
            invoice=invoice, quantity=1, date_tracked=datetime.date.today()
        )
        self.assertIsNotNone(hours)
        self.assertEqual(hours.quantity, 1)
        self.assertEqual(hours.invoice, invoice)
        self.assertEqual(hours.date_tracked, datetime.date.today())
        self.assertEqual(
            hours.slug_id, f"{slugify(invoice.title)}-{str(hours.id.int)[:6]}"
        )

    # def test_error_creating_hours_less_than_0(self):
    #     invoice = IntervalInvoiceFactory()
    #     with self.assertRaises(ValidationError):
    #         HoursLineItem.objects.create(
    #             invoice=invoice, quantity=-1, date_tracked=datetime.date.today()
    #         )
    #
    # def test_error_creating_hours_greater_than_24(self):
    #     invoice = IntervalInvoiceFactory()
    #     with self.assertRaises(ValidationError):
    #         HoursLineItem.objects.create(
    #             invoice=invoice, quantity=25, date_tracked=datetime.date.today()
    #         )

    def test_error_creating_hours_with_3_decimal_places(self):
        invoice = IntervalInvoiceFactory()
        with self.assertRaises(ValidationError):
            HoursLineItem.objects.create(
                invoice=invoice, quantity=2.556, date_tracked=datetime.date.today()
            )

    def test_error_creating_without_invoice(self):
        with self.assertRaises(ValidationError):
            HoursLineItem.objects.create(quantity=1, date_tracked=datetime.date.today())


class TestInvoice(TestCase):
    def test_invoice(self):
        user = UserFactory()

        def assert_valid(invoice):
            self.assertIsNotNone(invoice)
            self.assertIsNotNone(invoice.email_id)
            self.assertEqual(invoice.title, "Some title")
            self.assertEqual(invoice.user, user)
            self.assertEqual(invoice.rate, 100)
            self.assertEqual(invoice.client_name, "User")
            self.assertEqual(invoice.client_email, "user@test.com")
            self.assertEqual(invoice.next_date, next_date)
            self.assertEqual(invoice.last_date, datetime.date.today())
            self.assertEqual(invoice.slug_title, slugify(invoice.title))

        with self.subTest("Interval"):
            next_date = datetime.date.today() + datetime.timedelta(weeks=1)
            invoice = IntervalInvoice.objects.create(
                title="Some title",
                user=user,
                rate=100,
                client_name="User",
                client_email="user@test.com",
                invoice_interval="W",
                next_date=next_date,
                last_date=datetime.date.today(),
            )
            assert_valid(invoice)

        with self.subTest("Milestone"):
            next_date = datetime.date.today() + datetime.timedelta(weeks=1)
            invoice = MilestoneInvoice.objects.create(
                title="Some title",
                user=user,
                rate=100,
                client_name="User",
                client_email="user@test.com",
                milestone_total_steps="3",
                next_date=next_date,
                last_date=datetime.date.today(),
            )
            assert_valid(invoice)

        with self.subTest("Weekly"):
            next_date = datetime.date.today() + datetime.timedelta(weeks=1)
            invoice = WeeklyInvoice.objects.create(
                title="Some title",
                user=user,
                rate=100,
                client_name="User",
                client_email="user@test.com",
                next_date=next_date,
                last_date=datetime.date.today(),
            )
            assert_valid(invoice)

    def test_error_creating_invoice_rate_less_than_1(self):
        user = UserFactory()
        with self.assertRaises(ValidationError):
            IntervalInvoice.objects.create(
                title="Some title",
                user=user,
                rate=-10,
                client_name="User",
                client_email="user@test.com",
            )

    def test_error_creating_invoice_without_user(self):
        with self.assertRaises(ValidationError):
            IntervalInvoice.objects.create(
                title="Some title",
                rate=-10,
                client_name="User",
                client_email="user@test.com",
            )

    def test_error_creating_invoice_without_client_name(self):
        user = UserFactory()
        with self.assertRaises(ValidationError):
            IntervalInvoice.objects.create(
                title="Some title",
                user=user,
                rate=-10,
                client_email="user@test.com",
            )

    def test_error_creating_invoice_without_client_email(self):
        user = UserFactory()
        with self.assertRaises(ValidationError):
            IntervalInvoice.objects.create(
                title="Some title",
                user=user,
                rate=-10,
                client_name="User",
            )

    def test_invoice_calculate_next_date(self):
        today = datetime.date.today()
        invoice = IntervalInvoiceFactory(invoice_interval="W")
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
        invoice = IntervalInvoiceFactory(rate=50, last_date=two_days_ago)
        hours1 = HoursLineItemFactory(invoice=invoice, date_tracked=yesterday)
        hours2 = HoursLineItemFactory(invoice=invoice)
        hours_list = sorted([hours1, hours2], key=lambda x: x.date_tracked)

        hours_tracked, total_hours = invoice.get_hours_stats()
        self.assertListEqual(list(hours_tracked), hours_list)
        self.assertEqual(
            total_hours, (hours1.quantity + hours2.quantity) * invoice.rate
        )

    def test_get_hours_logged(self):
        two_days_ago = datetime.date.today() - datetime.timedelta(days=2)
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        invoice = IntervalInvoiceFactory(rate=50, last_date=two_days_ago)
        hours1 = HoursLineItemFactory(invoice=invoice, date_tracked=yesterday)
        hours2 = HoursLineItemFactory(invoice=invoice)
        hours_list = sorted([hours1, hours2], key=lambda x: x.date_tracked)

        hours_logged = invoice.get_hours_tracked()
        self.assertListEqual(list(hours_logged), hours_list)

    def test_get_hours_logged_since_last_date(self):
        three_days_ago = datetime.date.today() - datetime.timedelta(days=3)
        two_days_ago = datetime.date.today() - datetime.timedelta(days=2)
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        invoice = IntervalInvoiceFactory(rate=50, last_date=two_days_ago)
        hours1 = HoursLineItemFactory(invoice=invoice, date_tracked=yesterday)
        hours2 = HoursLineItemFactory(invoice=invoice)
        HoursLineItemFactory(invoice=invoice, date_tracked=three_days_ago)
        hours_list = sorted([hours1, hours2], key=lambda x: x.date_tracked)

        hours_logged = invoice.get_hours_tracked()
        self.assertListEqual(list(hours_logged), hours_list)

    def test_get_hours_logged_mid_cycle(self):
        """invoice.get_hours_tracked should filter out already sent hours"""
        invoice = IntervalInvoiceFactory(rate=50)
        sent_invoice = SentInvoiceFactory(invoice=invoice)
        HoursLineItemFactory(invoice=invoice, sent_invoice_id=sent_invoice.id)
        HoursLineItemFactory(invoice=invoice)
        HoursLineItemFactory(invoice=invoice)
        hours_logged = invoice.get_hours_tracked()
        self.assertEqual(len(hours_logged), 2)

    def test_get_budget_percentage(self):
        three_days_ago = datetime.date.today() - datetime.timedelta(days=3)
        two_days_ago = datetime.date.today() - datetime.timedelta(days=2)
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        invoice = IntervalInvoiceFactory(
            rate=50, last_date=two_days_ago, total_budget=1000
        )
        HoursLineItemFactory(quantity=3, invoice=invoice, date_tracked=three_days_ago)
        HoursLineItemFactory(quantity=1, invoice=invoice, date_tracked=yesterday)
        HoursLineItemFactory(quantity=2, invoice=invoice)
        # (6 hours * $50) / $1000
        self.assertEqual(invoice.budget_percentage(), Decimal("30.0"))

    def test_get_last_six_months(self):
        invoice = IntervalInvoiceFactory()
        hours1 = HoursLineItemFactory(invoice=invoice, quantity=1)
        sent_invoice_1 = SentInvoiceFactory(invoice=invoice, total_price=50)
        hours1.sent_invoice_id = sent_invoice_1.id
        hours2 = HoursLineItemFactory(
            invoice=invoice,
            quantity=2,
            date_tracked=datetime.date.today() - relativedelta(months=1),
        )
        sent_invoice_2 = SentInvoiceFactory(
            invoice=invoice,
            date_sent=datetime.date.today() - relativedelta(months=1),
            total_price=50,
        )
        hours2.sent_invoice_id = sent_invoice_2.id

        invoice.invoice_rate = 100
        invoice.save()

        hours3 = HoursLineItemFactory(
            invoice=invoice,
            quantity=3,
            date_tracked=datetime.date.today() - relativedelta(months=2),
        )
        sent_invoice_3 = SentInvoiceFactory(
            invoice=invoice,
            date_sent=datetime.date.today() - relativedelta(months=2),
            total_price=100,
        )
        hours3.sent_invoice_id = sent_invoice_3.id

        last_six = invoice.get_last_six_months()
        self.assertEqual(last_six[1][-1], 50.0)
        self.assertEqual(last_six[1][-2], 50.0)
        self.assertEqual(last_six[1][-3], 100.0)

    def test_get_last_six_months_including_weekly(self):
        invoice = WeeklyInvoiceFactory(rate=1000)
        SentInvoiceFactory(invoice=invoice, total_price=1000)
        SentInvoiceFactory(
            invoice=invoice,
            total_price=1000,
            date_sent=datetime.date.today() - relativedelta(months=1),
        )
        SentInvoiceFactory(
            invoice=invoice,
            total_price=1000,
            date_sent=datetime.date.today() - relativedelta(months=1),
        )
        SentInvoiceFactory(
            invoice=invoice,
            total_price=3000,
            date_sent=datetime.date.today() - relativedelta(months=2),
        )
        SentInvoiceFactory(
            invoice=invoice,
            total_price=4000,
            date_sent=datetime.date.today() - relativedelta(months=3),
        )
        last_six = invoice.get_last_six_months()
        self.assertEqual(last_six[1][-1], 1000.0)
        self.assertEqual(last_six[1][-2], 2000.0)
        self.assertEqual(last_six[1][-3], 3000.0)
        self.assertEqual(last_six[1][-4], 4000.0)

    def test_is_recurring_date_error(self):
        hours = HoursLineItemFactory()
        self.assertFalse(hours.is_recurring_date_today())

        hours = HoursLineItemFactory(recurring_logic={})
        self.assertFalse(hours.is_recurring_date_today())

        hours = HoursLineItemFactory(recurring_logic={"type": "Some other type"})
        self.assertFalse(hours.is_recurring_date_today())

    def test_is_recurring_daily_hours_date_today(self):
        start_week = get_starting_week_from_date(datetime.date.today()).isoformat()
        hours = HoursLineItemFactory(
            recurring_logic={
                "type": "recurring",
                "interval": "d",
                "starting_week": start_week,
            }
        )
        self.assertTrue(hours.is_recurring_date_today())

    def test_is_repeating_daily_hours_end_today(self):
        start_week = get_starting_week_from_date(datetime.date.today()).isoformat()
        hours = HoursLineItemFactory(
            recurring_logic={
                "type": "repeating",
                "interval": "d",
                "end_date": datetime.date.today().isoformat(),
                "starting_week": start_week,
            }
        )
        self.assertFalse(hours.is_recurring_date_today())

    def test_is_recurring_weekly_hours_date_today(self):
        start_week = get_starting_week_from_date(datetime.date.today()).isoformat()
        hours = HoursLineItemFactory(
            recurring_logic={
                "type": "recurring",
                "interval": "w",
                "interval_days": [get_date_parsed(datetime.date.today())],
                "starting_week": start_week,
            }
        )
        self.assertTrue(hours.is_recurring_date_today())

    def test_is_recurring_biweekly_hours_date_today(self):
        start_week = get_starting_week_from_date(datetime.date.today()).isoformat()
        hours = HoursLineItemFactory(
            recurring_logic={
                "type": "recurring",
                "interval": "b",
                "interval_days": [get_date_parsed(datetime.date.today())],
                "starting_week": start_week,
            }
        )
        self.assertTrue(hours.is_recurring_date_today())

    def test_is_recurring_biweekly_hours_date_today_not_valid_week(self):
        """Not the valid biweekly starting week iteration, either one week ago or ahead is fine"""
        start_week = get_starting_week_from_date(
            datetime.date.today() - datetime.timedelta(weeks=1)
        ).isoformat()
        hours = HoursLineItemFactory(
            recurring_logic={
                "type": "recurring",
                "interval": "b",
                "interval_days": [get_date_parsed(datetime.date.today())],
                "starting_week": start_week,
            }
        )
        self.assertFalse(hours.is_recurring_date_today())

    def test_is_recurring_weekly_hours_date_today_not_valid_day(self):
        """Not the valid weekly interval day"""
        start_week = get_starting_week_from_date(datetime.date.today()).isoformat()
        hours = HoursLineItemFactory(
            recurring_logic={
                "type": "recurring",
                "interval": "w",
                "interval_days": [
                    get_date_parsed(datetime.date.today() - datetime.timedelta(days=1))
                ],
                "starting_week": start_week,
            }
        )
        self.assertFalse(hours.is_recurring_date_today())


class TestSentInvoice(TestCase):
    def test_get_rendered_hourly_line_items(self):
        three_days_ago = datetime.date.today() - datetime.timedelta(days=3)
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        invoice = IntervalInvoiceFactory(rate=50, last_date=three_days_ago)
        hours1 = HoursLineItemFactory(
            quantity=1, invoice=invoice, date_tracked=yesterday
        )
        hours2 = HoursLineItemFactory(quantity=2, invoice=invoice)

        invoice.refresh_from_db()

        sent_invoice = SentInvoice.create(invoice=invoice)

        hours1.sent_invoice_id = sent_invoice.id
        hours1.save()
        hours2.sent_invoice_id = sent_invoice.id
        hours2.save()

        # If invoice's invoice_rate changes, make sure the sent invoice calculates the correct
        # hourly rate from total cost / sum(hours_tracked)
        invoice.rate = 25
        invoice.save()

        line_items = sent_invoice.get_rendered_line_items()
        self.assertInHTML(
            f"""
            <div>{floatformat(hours1.quantity, -2)} hours on {template_date(hours1.date_tracked, "M j")}</div>
            <div>${floatformat(hours1.quantity * invoice.rate, -2)}</div>
        """,
            line_items,
        )
        self.assertInHTML(
            f"""
                    <div>{floatformat(hours2.quantity, -2)} hours on {template_date(hours2.date_tracked, "M j")}</div>
                    <div>${floatformat(hours2.quantity * invoice.rate, -2)}</div>
                """,
            line_items,
        )

    def test_get_rendered_milestone_line_items(self):
        three_days_ago = datetime.date.today() - datetime.timedelta(days=3)
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        invoice = MilestoneInvoiceFactory(rate=50, last_date=three_days_ago)
        hours1 = HoursLineItemFactory(
            quantity=1, invoice=invoice, date_tracked=yesterday
        )
        hours2 = HoursLineItemFactory(quantity=2, invoice=invoice)

        invoice.refresh_from_db()

        sent_invoice = SentInvoice.create(invoice=invoice)

        hours1.sent_invoice_id = sent_invoice.id
        hours1.save()
        hours2.sent_invoice_id = sent_invoice.id
        hours2.save()

        # If invoice's invoice_rate changes, make sure the sent invoice calculates the correct
        # hourly rate from total cost / sum(hours_tracked)
        invoice.rate = 25
        invoice.save()

        line_items = sent_invoice.get_rendered_line_items()
        self.assertInHTML(
            f"""
            <div>{floatformat(hours1.quantity, -2)} hours on {template_date(hours1.date_tracked, "M j")}</div>
            <div>${floatformat(hours1.quantity * invoice.rate, -2)}</div>
        """,
            line_items,
        )
        self.assertInHTML(
            f"""
                    <div>{floatformat(hours2.quantity, -2)} hours on {template_date(hours2.date_tracked, "M j")}</div>
                    <div>${floatformat(hours2.quantity * invoice.rate, -2)}</div>
                """,
            line_items,
        )

    def test_get_rendered_weekly_line_items(self):
        invoice = WeeklyInvoiceFactory(rate=1000)
        invoice.refresh_from_db()
        sent_invoice = SentInvoice.create(invoice=invoice)

        line_items = sent_invoice.get_rendered_line_items()
        self.assertInHTML(
            f"""
                <div>Week of { template_date(sent_invoice.date_sent, "M j, Y")}</div>
                <div>${floatformat(sent_invoice.total_price,-2 )}</div>
            """,
            line_items,
        )

    def test_get_rendered_line_items_not_including_skipped(self):
        three_days_ago = datetime.date.today() - datetime.timedelta(days=3)
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        invoice = IntervalInvoiceFactory(rate=50, last_date=three_days_ago)
        hours1 = HoursLineItemFactory(
            quantity=0, invoice=invoice, date_tracked=yesterday
        )
        hours2 = HoursLineItemFactory(quantity=2, invoice=invoice)

        invoice.refresh_from_db()

        sent_invoice = SentInvoice.create(invoice=invoice)

        hours1.sent_invoice_id = sent_invoice.id
        hours1.save()
        hours2.sent_invoice_id = sent_invoice.id
        hours2.save()

        # If invoice's invoice_rate changes, make sure the sent invoice calculates the correct
        # hourly rate from total cost / sum(hours_tracked)
        invoice.rate = 25
        invoice.save()

        line_items = sent_invoice.get_rendered_line_items()
        with self.assertRaises(Exception):
            self.assertInHTML(
                f"""
                <div>{floatformat(hours1.quantity, -2)} hours on {template_date(hours1.date_tracked, "M j")}</div>
                <div>${floatformat(hours1.quantity * invoice.rate, -2)}</div>
                """,
                line_items,
            )
        self.assertInHTML(
            f"""
            <div>{floatformat(hours2.quantity, -2)} hours on {template_date(hours2.date_tracked, "M j")}</div>
            <div>${floatformat(hours2.quantity * invoice.rate, -2)}</div>
            """,
            line_items,
        )


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
        self.assertListEqual(user.phone_number_availability, ["Mon", "Tue", "Wed"])

    def test_settings_dict(self):
        user = UserFactory(phone_number_availability=["Mon", "Tue"])
        self.assertEqual(
            user.settings,
            {
                "phone_number_availability": ["Mon", "Tue"],
                "accounting_connected": None,
                "subscription_active": True,
            },
        )

    def test_get_active_invoices(self):
        user = UserFactory()
        InvoiceFactory(user=user)
        InvoiceFactory(user=user, is_archived=True)
        self.assertEqual(len(user.get_invoices), 1)

    def test_get_remaining_invoices(self):
        user = UserFactory()
        InvoiceFactory(user=user)
        InvoiceFactory(user=user)
        self.assertEqual(len(user.invoices_not_logged()), 2)

    def test_get_1_remaining_invoices(self):
        user = UserFactory()
        InvoiceFactory(user=user)
        InvoiceFactory()
        self.assertEqual(len(user.invoices_not_logged()), 1)

    def test_get_2_remaining_invoices(self):
        user = UserFactory()
        HoursLineItemFactory(invoice__user=user)
        InvoiceFactory(user=user)
        InvoiceFactory(user=user)
        self.assertEqual(len(user.invoices_not_logged()), 2)

    def test_get_1_remaining_invoices_logged_yesterday(self):
        user = UserFactory()
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        HoursLineItemFactory(invoice__user=user, date_tracked=yesterday)
        InvoiceFactory(user=user)
        self.assertEqual(len(user.invoices_not_logged()), 2)

    def test_get_1_remaining_invoices_logged_today(self):
        user = UserFactory()
        HoursLineItemFactory(invoice__user=user, date_tracked=datetime.date.today())
        InvoiceFactory(user=user)
        self.assertEqual(len(user.invoices_not_logged()), 1)

    def test_can_accept_payments(self):
        with self.subTest("Payouts enabled"):
            user = UserFactory(stripe_payouts_enabled=True)
            self.assertTrue(user.can_accept_payments)

        with self.subTest("Payouts not enabled"):
            user = UserFactory(stripe_payouts_enabled=False)
            self.assertFalse(user.can_accept_payments)

    def test_can_repeat_logged_days(self):
        user = UserFactory()
        hours_manager = HoursManager(user)
        with self.subTest("No previous day with logged hours"):
            self.assertEqual(hours_manager.can_repeat_previous_hours_logged(), 2)

        with self.subTest("Show repeat button"):
            HoursLineItemFactory(
                invoice=InvoiceFactory(user=user),
                date_tracked=datetime.date.today() - datetime.timedelta(days=1),
            )
            self.assertEqual(hours_manager.can_repeat_previous_hours_logged(), 1)

        with self.subTest("Don't show any message"):
            HoursLineItemFactory(
                invoice=InvoiceFactory(user=user),
                date_tracked=datetime.date.today(),
            )
            self.assertEqual(hours_manager.can_repeat_previous_hours_logged(), 0)

    @patch("stripe.Coupon.create")
    @patch("stripe.Subscription.modify")
    @patch("timary.services.stripe_service.StripeService.get_subscription")
    def test_user_referred_create_coupon(
        self, get_subscription_mock, stripe_modify_mock, stripe_coupon_mock
    ):
        stripe_modify_mock.return_value = {"id": "abc123"}
        stripe_coupon_mock.return_value = {"id": "abc123"}
        get_subscription_mock.return_value = {
            "discount": None,
            "id": "123",
        }
        user = UserFactory(stripe_subscription_recurring_price=29)
        self.assertEqual(user.add_referral_discount(), "abc123")
        user.refresh_from_db()
        self.assertEqual(user.stripe_subscription_recurring_price, 24)

    @patch("stripe.Coupon.create")
    @patch("stripe.Subscription.modify")
    @patch("stripe.Subscription.delete_discount")
    @patch("timary.services.stripe_service.StripeService.get_subscription")
    def test_user_referred_has_discount_and_allowed_another(
        self,
        get_subscription_mock,
        delete_discount_mock,
        stripe_modify_mock,
        stripe_coupon_mock,
    ):
        stripe_modify_mock.return_value = {"id": "abc123"}
        stripe_coupon_mock.return_value = {"id": "abc123"}
        delete_discount_mock.return_value = None
        get_subscription_mock.return_value = {
            "discount": {"coupon": {"amount_off": 500}},
            "id": "123",
        }
        user = UserFactory(stripe_subscription_recurring_price=24)
        # Business accounts are allowed one more coupon, which is modified to $10
        self.assertEqual(user.add_referral_discount(), "abc123")
        user.refresh_from_db()
        self.assertEqual(user.stripe_subscription_recurring_price, 19)

    def test_user_referred_dont_add_coupon_if_no_active_subscription(self):
        user = UserFactory()
        user.stripe_subscription_status = 3
        user.save()
        self.assertIsNone(user.add_referral_discount())
