import zoneinfo
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.template.defaultfilters import date as template_date
from django.template.defaultfilters import floatformat
from django.test import TestCase
from django.utils import timezone
from django.utils.text import slugify

from timary.hours_manager import HoursManager
from timary.models import (
    HoursLineItem,
    IntervalInvoice,
    LineItem,
    MilestoneInvoice,
    SentInvoice,
    User,
    WeeklyInvoice,
    default_tasks,
)
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
from timary.utils import (
    get_date_parsed,
    get_starting_week_from_date,
    get_users_localtime,
)


class TestLineItems(TestCase):
    def test_create(self):
        invoice = IntervalInvoiceFactory()
        line_item = LineItem.objects.create(invoice=invoice, quantity=2, unit_price=2.5)
        self.assertEqual(line_item.total_amount(), 5.0)


class TestDailyHours(TestCase):
    def test_create_daily_hours(self):
        invoice = IntervalInvoiceFactory()
        hours = HoursLineItem.objects.create(
            invoice=invoice, quantity=1, date_tracked=timezone.now()
        )
        self.assertIsNotNone(hours)
        self.assertEqual(hours.quantity, 1)
        self.assertEqual(hours.invoice, invoice)
        self.assertEqual(hours.date_tracked.date(), timezone.now().date())
        self.assertEqual(
            hours.slug_id, f"{slugify(invoice.title)}-{str(hours.id.int)[:6]}"
        )

    def test_error_creating_hours_with_3_decimal_places(self):
        invoice = IntervalInvoiceFactory()
        with self.assertRaises(ValidationError):
            HoursLineItem.objects.create(
                invoice=invoice, quantity=2.556, date_tracked=timezone.now()
            )

    def test_error_creating_without_invoice(self):
        with self.assertRaises(ValidationError):
            HoursLineItem.objects.create(quantity=1, date_tracked=timezone.now())

    def test_is_recurring_date_error(self):
        hours = HoursLineItemFactory()
        self.assertFalse(hours.is_recurring_date_today())

        hours = HoursLineItemFactory(recurring_logic={})
        self.assertFalse(hours.is_recurring_date_today())

        hours = HoursLineItemFactory(recurring_logic={"type": "Some other type"})
        self.assertFalse(hours.is_recurring_date_today())

    def test_is_recurring_daily_hours_date_today(self):
        start_week = get_starting_week_from_date(timezone.now()).isoformat()
        hours = HoursLineItemFactory(
            recurring_logic={
                "type": "recurring",
                "interval": "d",
                "starting_week": start_week,
            }
        )
        self.assertTrue(hours.is_recurring_date_today())

    def test_is_repeating_daily_hours_end_today(self):
        today = get_users_localtime(UserFactory())
        start_week = get_starting_week_from_date(today).isoformat()
        hours = HoursLineItemFactory(
            recurring_logic={
                "type": "repeating",
                "interval": "d",
                "end_date": today.isoformat(),
                "starting_week": start_week,
            }
        )
        self.assertFalse(hours.is_recurring_date_today())

    def test_is_recurring_weekly_hours_date_today(self):
        today = get_users_localtime(UserFactory())
        start_week = get_starting_week_from_date(today).isoformat()
        hours = HoursLineItemFactory(
            recurring_logic={
                "type": "recurring",
                "interval": "w",
                "interval_days": [get_date_parsed(today)],
                "starting_week": start_week,
            }
        )
        self.assertTrue(hours.is_recurring_date_today())

    def test_is_recurring_biweekly_hours_date_today(self):
        today = get_users_localtime(UserFactory())
        start_week = get_starting_week_from_date(today).isoformat()
        hours = HoursLineItemFactory(
            recurring_logic={
                "type": "recurring",
                "interval": "b",
                "interval_days": [get_date_parsed(today)],
                "starting_week": start_week,
            }
        )
        self.assertTrue(hours.is_recurring_date_today())

    def test_is_recurring_biweekly_hours_date_today_not_valid_week(self):
        """Not the valid biweekly starting week iteration, either one week ago or ahead is fine"""
        today = get_users_localtime(UserFactory())
        start_week = get_starting_week_from_date(
            today - timezone.timedelta(weeks=1)
        ).isoformat()
        hours = HoursLineItemFactory(
            recurring_logic={
                "type": "recurring",
                "interval": "b",
                "interval_days": [get_date_parsed(today)],
                "starting_week": start_week,
            }
        )
        self.assertFalse(hours.is_recurring_date_today())

    def test_is_recurring_weekly_hours_date_today_not_valid_day(self):
        """Not the valid weekly interval day"""
        today = get_users_localtime(UserFactory())
        start_week = get_starting_week_from_date(today).isoformat()
        hours = HoursLineItemFactory(
            recurring_logic={
                "type": "recurring",
                "interval": "w",
                "interval_days": [get_date_parsed(today - timezone.timedelta(days=1))],
                "starting_week": start_week,
            }
        )
        self.assertFalse(hours.is_recurring_date_today())


class TestInvoice(TestCase):
    def test_invoice(self):
        user = UserFactory()

        def assert_valid(inv):
            self.assertIsNotNone(inv)
            self.assertIsNotNone(inv.email_id)
            self.assertEqual(inv.title, "Some title")
            self.assertEqual(inv.user, user)
            self.assertEqual(inv.rate, 100)
            self.assertEqual(inv.next_date.date(), next_date.date())
            self.assertEqual(inv.last_date.date(), timezone.now().date())
            self.assertEqual(inv.slug_title, slugify(inv.title))

        with self.subTest("Interval"):
            next_date = timezone.now() + timezone.timedelta(weeks=1)
            fake_client = ClientFactory()
            invoice = IntervalInvoice.objects.create(
                title="Some title",
                user=user,
                rate=100,
                client=fake_client,
                invoice_interval="W",
                next_date=next_date,
                last_date=timezone.now(),
            )
            assert_valid(invoice)

        with self.subTest("Milestone"):
            next_date = timezone.now() + timezone.timedelta(weeks=1)
            fake_client = ClientFactory()
            invoice = MilestoneInvoice.objects.create(
                title="Some title",
                user=user,
                rate=100,
                client=fake_client,
                milestone_total_steps="3",
                next_date=next_date,
                last_date=timezone.now(),
            )
            assert_valid(invoice)

        with self.subTest("Weekly"):
            next_date = timezone.now() + timezone.timedelta(weeks=1)
            fake_client = ClientFactory()
            invoice = WeeklyInvoice.objects.create(
                title="Some title",
                user=user,
                rate=100,
                client=fake_client,
                next_date=next_date,
                last_date=timezone.now(),
            )
            assert_valid(invoice)

    def test_error_creating_invoice_rate_less_than_1(self):
        user = UserFactory()
        fake_client = ClientFactory()
        with self.assertRaises(ValidationError):
            IntervalInvoice.objects.create(
                title="Some title", user=user, rate=-10, client=fake_client
            )

    def test_error_creating_invoice_without_user(self):
        fake_client = ClientFactory()
        with self.assertRaises(ValidationError):
            IntervalInvoice.objects.create(
                title="Some title", rate=-10, client=fake_client
            )

    def test_invoice_calculate_next_date(self):
        today = timezone.now().astimezone(tz=zoneinfo.ZoneInfo("America/New_York"))
        invoice = IntervalInvoiceFactory(invoice_interval="W")
        invoice.calculate_next_date()
        self.assertEqual(
            invoice.next_date.date(), (today + timezone.timedelta(weeks=1)).date()
        )

        invoice.invoice_interval = "B"
        invoice.calculate_next_date()
        self.assertEqual(
            invoice.next_date.date(), (today + timezone.timedelta(weeks=2)).date()
        )

        invoice.invoice_interval = "M"
        invoice.calculate_next_date()
        self.assertEqual(
            invoice.next_date.date(), (today + timezone.timedelta(weeks=4)).date()
        )

        invoice.invoice_interval = "Q"
        invoice.calculate_next_date()
        self.assertEqual(
            invoice.next_date.date(), (today + timezone.timedelta(weeks=12)).date()
        )

        invoice.invoice_interval = "Y"
        invoice.calculate_next_date()
        self.assertEqual(
            invoice.next_date.date(), (today + timezone.timedelta(weeks=52)).date()
        )
        self.assertEqual(invoice.last_date.date(), today.date())

    def test_get_hours_stats(self):
        two_days_ago = timezone.now() - timezone.timedelta(days=2)
        yesterday = timezone.now() - timezone.timedelta(days=1)
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
        two_days_ago = timezone.now() - timezone.timedelta(days=2)
        yesterday = timezone.now() - timezone.timedelta(days=1)
        invoice = IntervalInvoiceFactory(rate=50, last_date=two_days_ago)
        hours1 = HoursLineItemFactory(invoice=invoice, date_tracked=yesterday)
        hours2 = HoursLineItemFactory(invoice=invoice)
        hours_list = sorted([hours1, hours2], key=lambda x: x.date_tracked)

        hours_logged = invoice.get_hours_tracked()
        self.assertListEqual(list(hours_logged), hours_list)

    def test_get_hours_logged_since_last_date(self):
        three_days_ago = timezone.now() - timezone.timedelta(days=3)
        two_days_ago = timezone.now() - timezone.timedelta(days=2)
        yesterday = timezone.now() - timezone.timedelta(days=1)
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
        three_days_ago = timezone.now() - timezone.timedelta(days=3)
        two_days_ago = timezone.now() - timezone.timedelta(days=2)
        yesterday = timezone.now() - timezone.timedelta(days=1)
        invoice = IntervalInvoiceFactory(
            rate=50, last_date=two_days_ago, total_budget=1000
        )
        HoursLineItemFactory(quantity=3, invoice=invoice, date_tracked=three_days_ago)
        HoursLineItemFactory(quantity=1, invoice=invoice, date_tracked=yesterday)
        HoursLineItemFactory(quantity=2, invoice=invoice)
        # (6 hours * $50) / $1000
        self.assertEqual(invoice.budget_percentage(), Decimal("30.0"))

    @patch("timary.models.timezone")
    def test_get_last_six_months(self, date_mock):
        date_mock.now.return_value = timezone.datetime(2023, 2, 5)
        tz = zoneinfo.ZoneInfo("America/New_York")
        invoice = IntervalInvoiceFactory()
        hours1 = HoursLineItemFactory(
            invoice=invoice,
            quantity=1,
            date_tracked=timezone.datetime(2023, 2, 1, tzinfo=tz),
        )
        sent_invoice_1 = SentInvoiceFactory(
            invoice=invoice,
            total_price=50,
            date_sent=timezone.datetime(2023, 2, 1, tzinfo=tz),
        )
        hours1.sent_invoice_id = sent_invoice_1.id
        hours2 = HoursLineItemFactory(
            invoice=invoice,
            quantity=2,
            date_tracked=timezone.datetime(2023, 1, 10, tzinfo=tz),
        )
        sent_invoice_2 = SentInvoiceFactory(
            invoice=invoice,
            date_sent=timezone.datetime(2023, 1, 10, tzinfo=tz),
            total_price=50,
        )
        hours2.sent_invoice_id = sent_invoice_2.id

        invoice.invoice_rate = 100
        invoice.save()

        hours3 = HoursLineItemFactory(
            invoice=invoice,
            quantity=3,
            date_tracked=timezone.datetime(2022, 12, 10, tzinfo=tz),
        )
        sent_invoice_3 = SentInvoiceFactory(
            invoice=invoice,
            date_sent=timezone.datetime(2022, 12, 10, tzinfo=tz),
            total_price=100,
        )
        hours3.sent_invoice_id = sent_invoice_3.id

        last_six = invoice.get_last_six_months()
        self.assertEqual(last_six[1][-1], 50.0)
        self.assertEqual(last_six[1][-2], 50.0)
        self.assertEqual(last_six[1][-3], 100.0)

    @patch("timary.models.timezone")
    def test_get_last_six_months_including_weekly(self, date_mock):
        date_mock.now.return_value = timezone.datetime(2023, 2, 5)
        invoice = WeeklyInvoiceFactory(rate=1000)
        tz = zoneinfo.ZoneInfo("America/New_York")
        SentInvoiceFactory(
            invoice=invoice,
            total_price=1000,
            date_sent=timezone.datetime(2023, 2, 1, tzinfo=tz),
        )
        SentInvoiceFactory(
            invoice=invoice,
            total_price=1000,
            date_sent=timezone.datetime(2023, 1, 10, tzinfo=tz),
        )
        SentInvoiceFactory(
            invoice=invoice,
            total_price=1000,
            date_sent=timezone.datetime(2023, 1, 17, tzinfo=tz),
        )
        SentInvoiceFactory(
            invoice=invoice,
            total_price=3000,
            date_sent=timezone.datetime(2022, 12, 10, tzinfo=tz),
        )
        SentInvoiceFactory(
            invoice=invoice,
            total_price=4000,
            date_sent=timezone.datetime(2022, 11, 12, tzinfo=tz),
        )
        last_six = invoice.get_last_six_months()
        self.assertEqual(last_six[1][-1], 1000.0)
        self.assertEqual(last_six[1][-2], 2000.0)
        self.assertEqual(last_six[1][-3], 3000.0)
        self.assertEqual(last_six[1][-4], 4000.0)

    def test_single_invoice_cannot_send_invoice_if_draft_status(self):
        invoice = SingleInvoiceFactory(status=0)
        self.assertFalse(invoice.can_send_invoice())

    def test_single_invoice_can_send_invoice_if_final_status(self):
        invoice = SingleInvoiceFactory(status=1)
        self.assertTrue(invoice.can_send_invoice())

    def test_single_invoice_cannot_send_invoice_if_balance_zero(self):
        invoice = SingleInvoiceFactory(status=1, balance_due=0)
        self.assertFalse(invoice.can_send_invoice())

    def test_single_invoice_cannot_send_invoice_if_sent_invoice_is_pending(self):
        sent_invoice = SentInvoiceFactory(
            invoice=SingleInvoiceFactory(status=1),
            paid_status=SentInvoice.PaidStatus.PENDING,
        )
        self.assertFalse(sent_invoice.invoice.can_send_invoice())

    def test_single_invoice_can_send_invoice_if_sent_invoice_is_not_paid_yet(self):
        sent_invoice = SentInvoiceFactory(
            invoice=SingleInvoiceFactory(status=1),
            paid_status=SentInvoice.PaidStatus.NOT_STARTED,
        )
        self.assertTrue(sent_invoice.invoice.can_send_invoice())

    def test_single_invoice_update_total_price(self):
        single_invoice = SingleInvoiceFactory(
            discount_amount=1.0,
            tax_amount=6.25,
            late_penalty=True,
            late_penalty_amount=2,
            due_date=timezone.now() - timezone.timedelta(days=1),
        )
        _ = [
            LineItem.objects.create(invoice=single_invoice, quantity=1, unit_price=1)
            for _ in range(5)
        ]
        single_invoice.update_total_price()
        self.assertEqual(single_invoice.balance_due, 6.25)

    def test_single_invoice_get_sent_invoices(self):
        with self.subTest("Installments of 1 only have one sent invoice instance"):
            single_invoice = SingleInvoiceFactory(installments=1)
            sent_invoice = SentInvoiceFactory(invoice=single_invoice)
            self.assertEqual(single_invoice.get_sent_invoice(), sent_invoice)
            self.assertIsNone(single_invoice.get_installments_data())
        with self.subTest(
            "Installments of 2 or more get the same number of sent invoices when complete"
        ):
            single_invoice = SingleInvoiceFactory(installments=3)
            SentInvoiceFactory(invoice=single_invoice)
            SentInvoiceFactory(invoice=single_invoice)
            self.assertEqual(single_invoice.get_sent_invoice().count(), 2)
            self.assertEqual(single_invoice.get_installments_data(), (2, 3))

    def test_can_edit_single_invoice(self):
        with self.subTest("Single installment not pending payment yet"):
            invoice = SingleInvoiceFactory(installments=1)
            SentInvoiceFactory(invoice=invoice, paid_status=0)
            self.assertTrue(invoice.can_edit())
        with self.subTest("single installment payment is pending"):
            invoice = SingleInvoiceFactory(installments=1)
            SentInvoiceFactory(invoice=invoice, paid_status=1)
            self.assertFalse(invoice.can_edit())
        with self.subTest("Multiple installment not all payment paid yet"):
            invoice = SingleInvoiceFactory(installments=3)
            SentInvoiceFactory(invoice=invoice, paid_status=0)
            SentInvoiceFactory(invoice=invoice, paid_status=0)
            SentInvoiceFactory(invoice=invoice, paid_status=2)
            self.assertTrue(invoice.can_edit())
        with self.subTest("Multiple installment all payment is paid"):
            invoice = SingleInvoiceFactory(installments=3)
            SentInvoiceFactory(invoice=invoice, paid_status=2)
            SentInvoiceFactory(invoice=invoice, paid_status=2)
            SentInvoiceFactory(invoice=invoice, paid_status=2)
            self.assertFalse(invoice.can_edit())

    def test_single_update_next_installment_date(self):
        with self.subTest("Invoice still has left to send"):
            invoice = SingleInvoiceFactory(
                installments=3, next_installment_date=timezone.now()
            )
            SentInvoiceFactory(invoice=invoice)
            SentInvoiceFactory(invoice=invoice)
            invoice.update_next_installment_date()
            invoice.refresh_from_db()
            self.assertIsNotNone(invoice.next_installment_date)
        with self.subTest("Invoice still has none left to send"):
            invoice = SingleInvoiceFactory(installments=3)
            SentInvoiceFactory(invoice=invoice)
            SentInvoiceFactory(invoice=invoice)
            SentInvoiceFactory(invoice=invoice)
            invoice.update_next_installment_date()
            invoice.refresh_from_db()
            self.assertIsNone(invoice.next_installment_date)

    def test_get_installment_price(self):
        with self.subTest("No installment sent yet"):
            invoice = SingleInvoiceFactory(installments=4, balance_due=400)
            self.assertEqual(invoice.get_installment_price(), 100)
        with self.subTest("One or more installments send already"):
            invoice = SingleInvoiceFactory(installments=4, balance_due=1000)
            SentInvoiceFactory(invoice=invoice, total_price=250)
            # (1000 - 250) / (4 -1)
            # Only get remaining price after calculating total pending/paid so far
            self.assertEqual(invoice.get_installment_price(), 250)

    def test_multiple_installments_do_not_include_late_payment_in_total(self):
        """We only want to apply the late payment to the individual installments if they are each paid late"""
        invoice = SingleInvoiceFactory(
            installments=4, discount_amount=5, late_penalty=True, late_penalty_amount=20
        )
        LineItemFactory(invoice=invoice, quantity=1, unit_price=10)
        invoice.update_total_price()
        self.assertEqual(invoice.balance_due, 5)

    def test_render_installment_line_items(self):
        with self.subTest("No late payment"):
            invoice = SingleInvoiceFactory(installments=4, balance_due=100)
            line_item = LineItemFactory(invoice=invoice, quantity=1, unit_price=100)
            sent_invoice = SentInvoiceFactory(
                invoice=invoice, due_date=timezone.now() + timezone.timedelta(days=1)
            )
            rendered_line_items = invoice.render_line_items(
                sent_invoice_id=sent_invoice.id
            )
            # The line item and balance is broken up into 4 therefore 25 each installment.
            self.assertInHTML(
                f"""
                <div>{line_item.description}</div>
                <div>$25</div>
                """,
                rendered_line_items,
            )
        with self.subTest("With late payment added"):
            invoice = SingleInvoiceFactory(
                installments=4,
                balance_due=100,
                late_penalty=True,
                late_penalty_amount=10,
            )
            line_item = LineItemFactory(invoice=invoice, quantity=1, unit_price=100)
            sent_invoice = SentInvoiceFactory(
                invoice=invoice, due_date=timezone.now() - timezone.timedelta(days=1)
            )
            rendered_line_items = invoice.render_line_items(
                sent_invoice_id=sent_invoice.id
            )
            # The line item and balance is broken up into 4 therefore 25 each installment.
            self.assertInHTML(
                f"""
                       <div>{line_item.description}</div>
                       <div>$25</div>
                       """,
                rendered_line_items,
            )
            self.assertInHTML(
                """
                <div class="flex justify-between py-3 text-xl">
                    <div>Late Penalty Fee</div>
                    <div>$10</div>
                </div>
                <div class="text-sm -mt-3 pb-3">Penalty added because this is past due.</div>
                """,
                rendered_line_items,
            )

    def test_multiple_installments_invoice_is_client_synced(self):
        fake_client = ClientFactory(accounting_customer_id="abc123")
        invoice = SingleInvoiceFactory(installments=2, client=fake_client)
        self.assertTrue(invoice.is_client_synced())

    def test_single_installment_is_synced(self):
        fake_client = ClientFactory(accounting_customer_id="abc123")
        invoice = SingleInvoiceFactory(installments=1, client=fake_client)
        SentInvoiceFactory(invoice=invoice, accounting_invoice_id="abc123")
        self.assertTrue(invoice.is_client_synced())

    def test_milestone_steps_all_completed(self):
        invoice = MilestoneInvoiceFactory(milestone_step=3, milestone_total_steps=2)
        self.assertTrue(invoice.milestones_completed)

    def test_milestone_steps_not_all_complete(self):
        invoice = MilestoneInvoiceFactory(milestone_step=3, milestone_total_steps=4)
        self.assertFalse(invoice.milestones_completed)

    def test_milestone_steps_not_all_complete_has_to_be_greater_than_total_steps(self):
        invoice = MilestoneInvoiceFactory(milestone_step=3, milestone_total_steps=3)
        self.assertFalse(invoice.milestones_completed)


class TestSentInvoice(TestCase):
    def test_update_installments_price(self):
        invoice = SingleInvoiceFactory(installments=2, balance_due=100)
        sent_invoice = SentInvoiceFactory(invoice=invoice, total_price=100)
        LineItemFactory(
            invoice=invoice, sent_invoice_id=sent_invoice.id, quantity=1, unit_price=100
        )
        sent_invoice.update_installments()

        # Divide line items by # of installments and added them up for each sent invoice installment
        self.assertEqual(sent_invoice.total_price, 50)

    def test_is_payment_late(self):
        with self.subTest("Installments of 1 do not have due dates on sent invoices"):
            invoice = SingleInvoiceFactory(installments=1)
            sent_invoice = SentInvoiceFactory(
                invoice=invoice, due_date=timezone.now() - timezone.timedelta(days=1)
            )
            self.assertFalse(sent_invoice.is_payment_late())

        with self.subTest("If no late penalty set, then false"):
            invoice = SingleInvoiceFactory(installments=3)
            sent_invoice = SentInvoiceFactory(
                invoice=invoice, due_date=timezone.now() - timezone.timedelta(days=1)
            )
            self.assertFalse(sent_invoice.is_payment_late())

        with self.subTest("If current date is greater than due date set"):
            invoice = SingleInvoiceFactory(installments=3, late_penalty=True)
            sent_invoice = SentInvoiceFactory(
                invoice=invoice, due_date=timezone.now() - timezone.timedelta(days=1)
            )
            self.assertTrue(sent_invoice.is_payment_late())

    def test_get_rendered_hourly_line_items(self):
        three_days_ago = timezone.now() - timezone.timedelta(days=3)
        yesterday = timezone.now().astimezone(
            tz=zoneinfo.ZoneInfo("America/New_York")
        ) - timezone.timedelta(days=1)
        invoice_rate_snapshot = 50
        invoice = IntervalInvoiceFactory(
            rate=invoice_rate_snapshot, last_date=three_days_ago
        )
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
            <div>${floatformat(hours1.quantity * invoice_rate_snapshot, -2)}</div>
            """,
            line_items,
        )
        self.assertInHTML(
            f"""
            <div>{floatformat(hours2.quantity, -2)} hours on {template_date(hours2.date_tracked, "M j")}</div>
            <div>${floatformat(hours2.quantity * invoice_rate_snapshot, -2)}</div>
            """,
            line_items,
        )

    def test_get_rendered_milestone_line_items(self):
        three_days_ago = timezone.now() - timezone.timedelta(days=3)
        yesterday = timezone.now().astimezone(
            tz=zoneinfo.ZoneInfo("America/New_York")
        ) - timezone.timedelta(days=1)
        invoice_rate_snapshot = 50
        invoice = MilestoneInvoiceFactory(
            rate=invoice_rate_snapshot, last_date=three_days_ago
        )
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
            <div>${floatformat(hours1.quantity * invoice_rate_snapshot, -2)}</div>
            """,
            line_items,
        )
        self.assertInHTML(
            f"""
            <div>{floatformat(hours2.quantity, -2)} hours on {template_date(hours2.date_tracked, "M j")}</div>
            <div>${floatformat(hours2.quantity * invoice_rate_snapshot, -2)}</div>
            """,
            line_items,
        )

    def test_get_rendered_weekly_line_items(self):
        invoice = WeeklyInvoiceFactory(rate=1000)
        invoice.refresh_from_db()
        sent_invoice = SentInvoice.create(invoice=invoice)

        line_items = sent_invoice.get_rendered_line_items()
        date_sent = sent_invoice.date_sent.astimezone(
            tz=zoneinfo.ZoneInfo("America/New_York")
        )
        self.assertInHTML(
            f"""
            <div>Week of {template_date(date_sent, "M j, Y") }</div>
            <div>${floatformat(sent_invoice.total_price,-2 )}</div>
            """,
            line_items,
        )

    def test_get_rendered_line_items_not_including_skipped(self):
        three_days_ago = timezone.now() - timezone.timedelta(days=3)
        yesterday = timezone.now().astimezone(
            tz=zoneinfo.ZoneInfo("America/New_York")
        ) - timezone.timedelta(days=1)
        invoice_rate_snapshot = 50
        invoice = IntervalInvoiceFactory(
            rate=invoice_rate_snapshot, last_date=three_days_ago
        )
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
                <div>${floatformat(hours1.quantity * invoice_rate_snapshot, -2)}</div>
                """,
                line_items,
            )
        self.assertInHTML(
            f"""
            <div>{floatformat(hours2.quantity, -2)} hours on {template_date(hours2.date_tracked, "M j")}</div>
            <div>${floatformat(hours2.quantity * invoice_rate_snapshot, -2)}</div>
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
        IntervalInvoiceFactory(user=user)
        IntervalInvoiceFactory(user=user, is_archived=True)
        self.assertEqual(len(user.get_invoices), 1)

    def test_get_remaining_invoices(self):
        user = UserFactory()
        IntervalInvoiceFactory(user=user)
        IntervalInvoiceFactory(user=user)
        self.assertEqual(len(user.invoices_not_logged()), 2)

    def test_get_1_remaining_invoices(self):
        user = UserFactory()
        IntervalInvoiceFactory(user=user)
        IntervalInvoiceFactory()
        self.assertEqual(len(user.invoices_not_logged()), 1)

    def test_get_2_remaining_invoices(self):
        user = UserFactory()
        HoursLineItemFactory(invoice__user=user, invoice__sms_ping_today=True)
        IntervalInvoiceFactory(user=user)
        IntervalInvoiceFactory(user=user)
        self.assertEqual(len(user.invoices_not_logged()), 2)

    def test_get_1_remaining_invoices_logged_today(self):
        user = UserFactory()
        IntervalInvoiceFactory(user=user)
        invoice = IntervalInvoiceFactory(user=user, sms_ping_today=True)
        HoursLineItemFactory(invoice=invoice)
        self.assertEqual(len(user.invoices_not_logged()), 1)

    def test_filter_out_single_invoices_logged_today(self):
        user = UserFactory()
        HoursLineItemFactory(invoice__user=user, invoice__sms_ping_today=True)
        IntervalInvoiceFactory(user=user)
        SingleInvoiceFactory(user=user)
        self.assertEqual(len(user.invoices_not_logged()), 1)

    def test_can_accept_payments(self):
        with self.subTest("Payouts enabled"):
            user = UserFactory(stripe_payouts_enabled=True)
            self.assertTrue(user.can_accept_payments)

        with self.subTest("Payouts not enabled"):
            user = UserFactory(stripe_payouts_enabled=False)
            self.assertFalse(user.can_accept_payments)

    @patch("timary.querysets.get_users_localtime")
    def test_can_repeat_logged_days(self, date_mock):
        date_mock.return_value = timezone.datetime(
            2023, 1, 10, tzinfo=zoneinfo.ZoneInfo("America/New_York")
        )
        user = UserFactory()
        hours_manager = HoursManager(user)
        with self.subTest("No previous day with logged hours"):
            self.assertEqual(hours_manager.can_repeat_previous_hours_logged(), 2)

        with self.subTest("Show repeat button"):
            HoursLineItemFactory(
                invoice=IntervalInvoiceFactory(user=user),
                date_tracked=timezone.now() - timezone.timedelta(days=1),
            )
            self.assertEqual(hours_manager.can_repeat_previous_hours_logged(), 1)

        with self.subTest("Don't show any message"):
            HoursLineItemFactory(
                invoice=IntervalInvoiceFactory(user=user),
                date_tracked=timezone.now(),
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

    def test_onboarding_tasks_not_all_complete(self):
        tasks = default_tasks()
        tasks["first_client"] = True
        tasks["first_invoice"] = True
        user = UserFactory(onboarding_tasks=tasks)
        tasks_done = user.onboarding_tasks_done()
        self.assertFalse(tasks_done[0])
        self.assertEqual(tasks_done[1], 33)

    def test_onboarding_tasks_all_complete(self):
        tasks = default_tasks()
        for k, _ in tasks.items():
            tasks[k] = True
        user = UserFactory(onboarding_tasks=tasks)
        tasks_done = user.onboarding_tasks_done()
        self.assertTrue(tasks_done[0])
        self.assertIsNone(tasks_done[1])
