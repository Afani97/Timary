import zoneinfo
from datetime import date, datetime, timedelta
from unittest.mock import patch

from django.conf import settings
from django.core import mail
from django.template.defaultfilters import date as template_date
from django.template.defaultfilters import floatformat
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from timary.models import HoursLineItem, SentInvoice, User
from timary.tasks import (
    gather_invoice_installments,
    gather_invoices,
    gather_recurring_hours,
    gather_single_invoices_before_due_date,
    send_invoice,
    send_invoice_installment,
    send_invoice_preview,
    send_invoice_reminder,
    send_weekly_updates,
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
from timary.utils import get_date_parsed, get_starting_week_from_date


class TestGatherInvoices(TestCase):
    @patch("timary.tasks.async_task")
    def test_gather_0_invoices(self, send_invoice_mock):
        send_invoice_mock.return_value = None
        invoices_sent = gather_invoices()
        self.assertEqual("Invoices sent: 0", invoices_sent)

    @patch("timary.tasks.async_task")
    def test_gather_0_invoices_for_today(self, send_invoice_mock):
        send_invoice_mock.return_value = None
        HoursLineItemFactory(
            invoice__next_date=timezone.now() + timezone.timedelta(days=2)
        )
        HoursLineItemFactory(
            invoice__next_date=timezone.now() - timezone.timedelta(days=1)
        )
        invoices_sent = gather_invoices()
        self.assertEqual("Invoices sent: 0", invoices_sent)

    @patch("timary.tasks.async_task")
    def test_gather_0_invoices_with_next_date_null(self, send_invoice_mock):
        send_invoice_mock.return_value = None
        HoursLineItemFactory(invoice__next_date=None)
        invoices_sent = gather_invoices()
        self.assertEqual("Invoices sent: 0", invoices_sent)

    @patch("timary.tasks.async_task")
    def test_gather_0_invoices_if_user_are_not_active(self, send_invoice_mock):
        send_invoice_mock.return_value = None
        HoursLineItemFactory(
            invoice__next_date=timezone.now() + timezone.timedelta(days=2),
            invoice__user__stripe_subscription_status=User.StripeSubscriptionStatus.INACTIVE,
        )
        invoices_sent = gather_invoices()
        self.assertEqual("Invoices sent: 0", invoices_sent)

    @patch("timary.tasks.async_task")
    def test_gather_1_invoice_for_today(self, send_invoice_mock):
        send_invoice_mock.return_value = None
        HoursLineItemFactory(invoice__next_date=timezone.now())
        HoursLineItemFactory()
        invoices_sent = gather_invoices()
        self.assertEqual("Invoices sent: 1", invoices_sent)

    @patch("timary.tasks.async_task")
    def test_gather_3_invoices_for_today(self, send_invoice_mock):
        send_invoice_mock.return_value = None
        HoursLineItemFactory(invoice__next_date=timezone.now())
        HoursLineItemFactory(invoice__next_date=timezone.now())
        HoursLineItemFactory(invoice__next_date=timezone.now())
        invoices_sent = gather_invoices()
        self.assertEqual("Invoices sent: 3", invoices_sent)

    @patch("timary.tasks.async_task")
    def test_gather_0_invoice_previews_for_tomorrow_if_user_not_active(
        self, send_invoice_mock
    ):
        send_invoice_mock.return_value = None
        HoursLineItemFactory(
            invoice__next_date=timezone.now() + timezone.timedelta(days=1),
            invoice__user__stripe_subscription_status=User.StripeSubscriptionStatus.INACTIVE,
        )
        invoices_sent = gather_invoices()
        self.assertEqual("Invoices sent: 0", invoices_sent)

    @patch("timary.tasks.async_task")
    def test_gather_1_invoice_preview_for_tomorrow(self, send_invoice_mock):
        send_invoice_mock.return_value = None
        HoursLineItemFactory(
            invoice__next_date=timezone.now() + timezone.timedelta(days=1)
        )
        invoices_sent = gather_invoices()
        self.assertEqual("Invoices sent: 1", invoices_sent)

    @patch("timary.tasks.async_task")
    def test_gather_3_invoice_previews_for_tomorrow(self, send_invoice_mock):
        send_invoice_mock.return_value = None
        HoursLineItemFactory(
            invoice__next_date=timezone.now() + timezone.timedelta(days=1)
        )
        HoursLineItemFactory(
            invoice__next_date=timezone.now() + timezone.timedelta(days=1)
        )
        HoursLineItemFactory(
            invoice__next_date=timezone.now() + timezone.timedelta(days=1)
        )
        invoices_sent = gather_invoices()
        self.assertEqual("Invoices sent: 3", invoices_sent)

    @patch("timary.tasks.async_task")
    def test_gather_1_invoice_and_invoice_previews(self, send_invoice_mock):
        send_invoice_mock.return_value = None
        HoursLineItemFactory(invoice__next_date=timezone.now())
        HoursLineItemFactory(
            invoice__next_date=timezone.now() + timezone.timedelta(days=1)
        )
        HoursLineItemFactory(
            invoice__next_date=timezone.now() + timezone.timedelta(days=2)
        )
        invoices_sent = gather_invoices()
        self.assertEqual("Invoices sent: 2", invoices_sent)

    @patch("timary.tasks.async_task")
    def test_gather_1_invoice_and_not_milestone_invoice(self, send_invoice_mock):
        send_invoice_mock.return_value = None
        milestone_invoice = MilestoneInvoiceFactory()
        HoursLineItemFactory(invoice=milestone_invoice)
        HoursLineItemFactory(invoice__next_date=timezone.now())
        invoices_sent = gather_invoices()
        self.assertEqual("Invoices sent: 1", invoices_sent)

    @patch("timary.tasks.timezone")
    @patch("timary.tasks.async_task")
    def test_gather_1_invoice_monday_for_weekly(self, send_invoice_mock, today_mock):
        send_invoice_mock.return_value = None
        today_mock.now.return_value = timezone.datetime(
            2022, 8, 22, tzinfo=zoneinfo.ZoneInfo("America/New_York")
        )
        WeeklyInvoiceFactory()
        invoices_sent = gather_invoices()
        self.assertEqual("Invoices sent: 1", invoices_sent)

    @patch("timary.tasks.timezone")
    def test_gather_0_invoice_tuesday_for_weekly(self, today_mock):
        today_mock.now.return_value = timezone.datetime(
            2022, 8, 23, tzinfo=zoneinfo.ZoneInfo("America/New_York")
        )
        WeeklyInvoiceFactory()
        invoices_sent = gather_invoices()
        self.assertEqual("Invoices sent: 0", invoices_sent)

    @patch("timary.tasks.timezone")
    def test_gather_0_invoice_for_weekly_if_user_not_active(self, today_mock):
        today_mock.now.return_value = timezone.datetime(
            2022, 8, 23, tzinfo=zoneinfo.ZoneInfo("America/New_York")
        )
        WeeklyInvoiceFactory(
            user__stripe_subscription_status=User.StripeSubscriptionStatus.INACTIVE
        )
        invoices_sent = gather_invoices()
        self.assertEqual("Invoices sent: 0", invoices_sent)


class TestGatherInvoiceInstallments(TestCase):
    @patch("timary.tasks.async_task")
    def test_gather_0_installments(self, send_installment_mock):
        send_installment_mock.return_value = None
        installments_sent = gather_invoice_installments()
        self.assertEqual("Installments sent: 0", installments_sent)

    @patch("timary.tasks.async_task")
    def test_gather_0_installments_for_today(self, send_installment_mock):
        send_installment_mock.return_value = None
        SingleInvoiceFactory(
            next_installment_date=timezone.now() + timezone.timedelta(days=2)
        )
        SingleInvoiceFactory(
            next_installment_date=timezone.now() - timezone.timedelta(days=1)
        )
        installments_sent = gather_invoice_installments()
        self.assertEqual("Installments sent: 0", installments_sent)

    @patch("timary.tasks.async_task")
    def test_gather_installments_excluding_archived_and_inactive_subscriptions(
        self, send_installment_mock
    ):
        send_installment_mock.return_value = None
        SingleInvoiceFactory(next_installment_date=timezone.now(), is_archived=True)
        SingleInvoiceFactory(
            next_installment_date=timezone.now(), user__stripe_subscription_status=3
        )
        installments_sent = gather_invoice_installments()
        self.assertEqual("Installments sent: 0", installments_sent)

    @patch("timary.tasks.async_task")
    def test_gather_installments_for_today(self, send_installment_mock):
        send_installment_mock.return_value = None
        SingleInvoiceFactory(next_installment_date=timezone.now())
        SingleInvoiceFactory(next_installment_date=timezone.now())
        installments_sent = gather_invoice_installments()
        self.assertEqual("Installments sent: 2", installments_sent)

    @patch("timary.tasks.async_task")
    def test_gather_installments_for_today_exluding_not_allowed(
        self, send_installment_mock
    ):
        send_installment_mock.return_value = None
        SingleInvoiceFactory(next_installment_date=timezone.now())
        SingleInvoiceFactory(next_installment_date=timezone.now(), is_archived=True)
        SingleInvoiceFactory(
            next_installment_date=timezone.now(), user__stripe_subscription_status=3
        )
        installments_sent = gather_invoice_installments()
        self.assertEqual("Installments sent: 1", installments_sent)


class TestGatherHours(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.local_time = timezone.now()
        cls.start_week = get_starting_week_from_date(cls.local_time).isoformat()
        cls.next_week = get_starting_week_from_date(
            cls.local_time + timezone.timedelta(weeks=1)
        ).isoformat()
        cls.date_tracked = cls.local_time - timezone.timedelta(days=1)

    def test_gather_0_hours(self):
        hours_added = gather_recurring_hours()
        self.assertEqual("0 hours added.", hours_added)
        self.assertEquals(HoursLineItem.objects.count(), 0)

    def test_gather_0_hours_with_archived_invoice(self):
        HoursLineItemFactory(
            date_tracked=self.date_tracked,
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

    def test_gather_0_hours_if_already_tracked_today(self):
        HoursLineItemFactory(
            date_tracked=timezone.now().astimezone(
                tz=zoneinfo.ZoneInfo("America/New_York")
            ),
            recurring_logic={
                "type": "repeating",
                "interval": "d",
                "starting_week": self.start_week,
                "end_date": self.next_week,
            },
        )
        hours_added = gather_recurring_hours()
        self.assertEqual("0 hours added.", hours_added)
        self.assertEquals(HoursLineItem.objects.count(), 1)

    def test_gather_1_hour(self):
        HoursLineItemFactory(
            date_tracked=self.date_tracked,
            recurring_logic={
                "type": "repeating",
                "interval": "d",
                "starting_week": self.start_week,
                "end_date": self.next_week,
            },
        )
        hours_added = gather_recurring_hours()
        self.assertEqual("1 hours added.", hours_added)
        self.assertEquals(HoursLineItem.objects.count(), 2)

    @patch("timary.tasks.timezone")
    def test_gather_2_hour(self, date_mock):
        date_mock.now.return_value = self.local_time
        HoursLineItemFactory(
            date_tracked=self.date_tracked,
            recurring_logic={
                "type": "repeating",
                "interval": "d",
                "starting_week": self.start_week,
                "end_date": self.next_week,
            },
        )
        HoursLineItemFactory(
            date_tracked=self.date_tracked,
            recurring_logic={
                "type": "repeating",
                "interval": "w",
                "interval_days": [
                    get_date_parsed(self.date_tracked.date()),
                    get_date_parsed(self.local_time.date()),
                ],
                "starting_week": self.start_week,
                "end_date": self.next_week,
            },
        )
        hours_added = gather_recurring_hours()
        self.assertEqual("2 hours added.", hours_added)
        self.assertEquals(HoursLineItem.objects.count(), 4)

    def test_passing_recurring_logic(self):
        hours = HoursLineItemFactory(
            date_tracked=self.date_tracked,
            recurring_logic={
                "type": "repeating",
                "interval": "d",
                "starting_week": self.start_week,
                "end_date": self.next_week,
            },
        )
        hours_added = gather_recurring_hours()
        self.assertEqual("1 hours added.", hours_added)
        self.assertEquals(HoursLineItem.objects.count(), 2)

        hours.refresh_from_db()
        self.assertIsNone(hours.recurring_logic)

    def test_hours_not_scheduled_do_not_get_created(self):
        hours = HoursLineItemFactory(
            date_tracked=self.date_tracked,
            recurring_logic={
                "type": "repeating",
                "interval": "w",
                "interval_days": [
                    get_date_parsed(
                        (timezone.now() - timezone.timedelta(days=1)).date()
                    )
                ],
                "starting_week": self.start_week,
                "end_date": self.next_week,
            },
        )
        hours_added = gather_recurring_hours()
        self.assertEqual("0 hours added.", hours_added)
        self.assertEquals(HoursLineItem.objects.count(), 1)

        hours.refresh_from_db()
        self.assertIsNotNone(hours.recurring_logic)

    @patch("timary.models.HoursLineItem.update_recurring_starting_weeks")
    @patch("timary.tasks.timezone")
    def test_refresh_starting_weeks_on_saturday(self, date_mock, update_weeks_mock):
        date_mocked = timezone.datetime(
            2022, 12, 31, tzinfo=zoneinfo.ZoneInfo("America/New_York")
        )
        date_mock.now.return_value = date_mocked
        update_weeks_mock.return_value = None
        HoursLineItemFactory(
            recurring_logic={
                "type": "recurring",
                "interval": "b",
                "starting_week": get_starting_week_from_date(date_mocked).isoformat(),
                "interval_days": ["mon", "tue"],
            }
        )
        hours_added = gather_recurring_hours()
        self.assertEqual("0 hours added.", hours_added)
        self.assertEquals(HoursLineItem.objects.count(), 1)
        self.assertTrue(update_weeks_mock.assert_called_once)

    @patch("timary.models.HoursLineItem.cancel_recurring_hour")
    @patch("timary.tasks.timezone")
    def test_cancel_previous_recurring_logic(self, date_mock, cancel_hours_mock):
        """Prevent double stacking of hours, have one recurring instance at a time"""
        date_mock.now.return_value = timezone.datetime(
            2022, 12, 31, tzinfo=zoneinfo.ZoneInfo("America/New_York")
        )
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


class TestGatherAndSendSingleInvoices(TestCase):
    def setUp(self) -> None:
        self.todays_date = timezone.now()
        self.current_month = date.strftime(self.todays_date, "%m/%Y")

    @classmethod
    def extract_html(cls):
        s = mail.outbox[0].message().as_string()
        start = s.find("<body>") + len("<body>")
        end = s.find("</body>")
        message = s[start:end]
        return message

    @patch("timary.tasks.async_task")
    def test_gather_1_invoice_due_for_tomorrow(self, send_invoice_mock):
        send_invoice_mock.return_value = None
        invoice = SingleInvoiceFactory(
            due_date=timezone.now() + timezone.timedelta(days=1)
        )
        LineItemFactory(invoice=invoice)
        invoices_sent = gather_single_invoices_before_due_date()
        self.assertEqual("Invoices sent: 1", invoices_sent)

    @patch("timary.tasks.async_task")
    def test_gather_1_invoice_due_in_two_days(self, send_invoice_mock):
        send_invoice_mock.return_value = None
        invoice = SingleInvoiceFactory(
            due_date=timezone.now() + timezone.timedelta(days=2)
        )
        LineItemFactory(invoice=invoice)
        invoices_sent = gather_single_invoices_before_due_date()
        self.assertEqual("Invoices sent: 1", invoices_sent)

    @patch("timary.tasks.async_task")
    def test_gather_1_invoice_due_tomorrow_and_in_two_days(self, send_invoice_mock):
        send_invoice_mock.return_value = None
        invoice = SingleInvoiceFactory(
            due_date=timezone.now() + timezone.timedelta(days=1)
        )
        LineItemFactory(invoice=invoice)
        second_invoice = SingleInvoiceFactory(
            due_date=timezone.now() + timezone.timedelta(days=2)
        )
        LineItemFactory(invoice=second_invoice)
        invoices_sent = gather_single_invoices_before_due_date()
        self.assertEqual("Invoices sent: 2", invoices_sent)

    @patch("timary.tasks.async_task")
    def test_gather_0_invoice_due_since_none_are_ready(self, send_invoice_mock):
        send_invoice_mock.return_value = None
        invoice = SingleInvoiceFactory(
            due_date=timezone.now() + timezone.timedelta(days=5)
        )
        LineItemFactory(invoice=invoice)
        invoices_sent = gather_single_invoices_before_due_date()
        self.assertEqual("Invoices sent: 0", invoices_sent)

    @patch("timary.tasks.async_task")
    def test_gather_0_invoice_that_are_not_archived(self, send_invoice_mock):
        send_invoice_mock.return_value = None
        invoice = SingleInvoiceFactory(
            due_date=timezone.now() + timezone.timedelta(days=1),
            is_archived=True,
        )
        LineItemFactory(invoice=invoice)
        invoices_sent = gather_single_invoices_before_due_date()
        self.assertEqual("Invoices sent: 0", invoices_sent)

    @patch("timary.tasks.async_task")
    def test_gather_0_invoice_that_user_is_not_active(self, send_invoice_mock):
        send_invoice_mock.return_value = None
        invoice = SingleInvoiceFactory(
            due_date=timezone.now() + timezone.timedelta(days=1),
            user__stripe_subscription_status=User.StripeSubscriptionStatus.INACTIVE,
        )
        LineItemFactory(invoice=invoice)
        invoices_sent = gather_single_invoices_before_due_date()
        self.assertEqual("Invoices sent: 0", invoices_sent)

    @patch("timary.tasks.async_task")
    def test_gather_1_invoice_due_that_is_available(self, send_invoice_mock):
        send_invoice_mock.return_value = None
        invoice = SingleInvoiceFactory(
            due_date=timezone.now() + timezone.timedelta(days=1)
        )
        LineItemFactory(invoice=invoice)
        SingleInvoiceFactory(
            due_date=timezone.now() + timezone.timedelta(days=1),
            user__stripe_subscription_status=User.StripeSubscriptionStatus.INACTIVE,
        )
        SingleInvoiceFactory(
            due_date=timezone.now() + timezone.timedelta(days=1),
            is_archived=True,
        )
        invoices_sent = gather_single_invoices_before_due_date()
        self.assertEqual("Invoices sent: 1", invoices_sent)

    def test_send_invoice_reminder(self):
        fake_client = ClientFactory()
        invoice = SingleInvoiceFactory(client=fake_client)
        LineItemFactory(invoice=invoice)
        send_invoice_reminder(invoice.id)
        self.assertEquals(len(mail.outbox), 1)
        self.assertEquals(
            mail.outbox[0].subject,
            f"{invoice.title}'s Invoice from {invoice.user.first_name} for {self.current_month}",
        )
        self.assertEquals(SentInvoice.objects.count(), 1)

    def test_do_not_send_invoice_reminder_if_pending_or_paid(self):
        fake_client = ClientFactory()
        invoice = SingleInvoiceFactory(client=fake_client)
        LineItemFactory(invoice=invoice)
        sent_invoice = SentInvoiceFactory(
            invoice=invoice,
            paid_status=SentInvoice.PaidStatus.PAID,
            date_sent=timezone.now() - timezone.timedelta(days=1),
        )
        send_invoice_reminder(invoice.id)
        self.assertEquals(len(mail.outbox), 0)
        self.assertNotEqual(sent_invoice.date_sent.date(), timezone.now().date())


class TestSendInvoice(TestCase):
    def setUp(self) -> None:
        self.todays_date = timezone.now()
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
        two_days_ago = self.todays_date - timezone.timedelta(days=2)
        yesterday = self.todays_date - timezone.timedelta(days=1)
        invoice = IntervalInvoiceFactory(
            last_date=self.todays_date - timezone.timedelta(days=3)
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
            (h1.quantity + h2.quantity + h3.quantity) * invoice.rate,
        )

    def test_sent_invoices_only_2_hours(self):
        yesterday = self.todays_date - timezone.timedelta(days=1)
        invoice = IntervalInvoiceFactory(
            last_date=self.todays_date - timezone.timedelta(days=1)
        )
        HoursLineItemFactory(
            date_tracked=self.todays_date - timezone.timedelta(days=2), invoice=invoice
        )
        h2 = HoursLineItemFactory(date_tracked=yesterday, invoice=invoice)
        h3 = HoursLineItemFactory(date_tracked=self.todays_date, invoice=invoice)

        send_invoice(invoice.id)
        self.assertEquals(len(mail.outbox), 1)
        self.assertEquals(SentInvoice.objects.count(), 1)

        sent_invoice = SentInvoice.objects.first()
        self.assertEquals(
            sent_invoice.total_price,
            (h2.quantity + h3.quantity) * invoice.rate,
        )

    def test_dont_send_invoice_if_no_tracked_hours(self):
        hours = HoursLineItemFactory(
            date_tracked=(self.todays_date - timezone.timedelta(days=1))
        )
        hours.invoice.last_date = self.todays_date
        hours.invoice.save()
        hours.save()

        send_invoice(hours.invoice.id)
        self.assertEqual(len(mail.outbox), 0)

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
        invoice = IntervalInvoiceFactory(rate=25)
        # Save last date before it's updated in send_invoice method to test email contents below
        hours_1 = HoursLineItemFactory(invoice=invoice, quantity=1)
        HoursLineItemFactory(invoice=invoice, quantity=2)
        HoursLineItemFactory(invoice=invoice, quantity=3)

        send_invoice(invoice.id)
        invoice.refresh_from_db()

        html_message = TestSendInvoice.extract_html()
        with self.subTest("Testing title"):
            msg = f"""
            <div class="mt-0 mb-4 text-3xl font-semibold text-left">Hi {invoice.client.name},</div>
            <div class="my-2 text-xl leading-7">Thanks for using Timary.
            This is an invoice for {invoice.user.first_name}'s services.</div>
            """
            self.assertInHTML(msg, html_message)

        with self.subTest("Testing amount due"):
            msg = "<strong>Amount Due: $155</strong>"
            self.assertInHTML(msg, html_message)

        with self.subTest("Testing one day details"):
            formatted_date = template_date(
                hours_1.date_tracked,
                "M j",
            )
            msg = f"""
            <div>1 hours on { formatted_date }</div>
            <div>$25</div>
            """
            self.assertInHTML(msg, html_message)

    def test_invoice_preview_context(self):
        user = UserFactory()
        invoice = IntervalInvoiceFactory(
            user=user,
            rate=25,
            next_date=timezone.now() - timezone.timedelta(days=1),
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
            <div class="mt-0 mb-4 text-3xl font-semibold text-left">Hi {invoice.client.name},</div>
            <div class="my-2 text-xl leading-7">Thanks for using Timary.
            This is an invoice for {invoice.user.first_name}'s services.</div>
            """
            self.assertInHTML(msg, html_message)

        with self.subTest("Testing amount due"):
            msg = "<strong>Amount Due: $150</strong>"
            self.assertInHTML(msg, html_message)

        with self.subTest("Testing one day details"):
            formatted_date = template_date(
                hours_1.date_tracked,
                "M j",
            )
            msg = f"""
            <div>1 hours on { formatted_date }</div>
            <div>$25</div>
            """
            self.assertInHTML(msg, html_message)

    def test_invoice_cannot_accept_payments_without_stripe_enabled(self):
        fake_client = ClientFactory()
        invoice = IntervalInvoiceFactory(
            user__stripe_payouts_enabled=False, client=fake_client
        )
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
        invoice = IntervalInvoiceFactory(user__stripe_payouts_enabled=True)
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
        invoice = WeeklyInvoiceFactory(rate=1200)
        HoursLineItemFactory(invoice=invoice)
        send_invoice(invoice.id)

        sent_invoice = SentInvoice.objects.filter(invoice__id=invoice.id).first()
        date_sent = sent_invoice.date_sent.astimezone(
            tz=zoneinfo.ZoneInfo("America/New_York")
        )

        weekly_log_item = f"""
        <div class="flex justify-between py-3 text-xl">
            <div>Week of { template_date(date_sent, "M j, Y") }</div>
            <div>$1200</div>
        </div>
        """
        html_message = TestSendInvoice.extract_html()
        self.assertInHTML(weekly_log_item, html_message)

    @patch("timary.services.twilio_service.TwilioClient.sent_payment_success")
    def test_paid_invoice_receipt(self, twilio_mock):
        twilio_mock.return_value = None
        invoice = IntervalInvoiceFactory(
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
            <div class="mt-0 mb-4 text-3xl font-semibold text-left">Hi {invoice.client.name},</div>
            <div class="my-2 text-xl leading-7">Thanks for using Timary.
            This is a copy of the invoice paid for Bob's services on
            {template_date(sent_invoice.date_sent, "M. j, Y")}.
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


class TestSendInvoiceInstallment(TestCase):
    def setUp(self) -> None:
        self.todays_date = timezone.now()
        self.current_month = date.strftime(self.todays_date, "%m/%Y")

    @classmethod
    def extract_html(cls):
        s = mail.outbox[0].message().as_string()
        start = s.find("<body>") + len("<body>")
        end = s.find("</body>")
        message = s[start:end]
        return message

    def test_send_installment(self):
        invoice = SingleInvoiceFactory(
            next_installment_date=timezone.now(), installments=2, balance_due=100
        )
        LineItemFactory(invoice=invoice, quantity=1, unit_price=100)
        send_invoice_installment(invoice.id)
        sent_invoice = invoice.get_sent_invoice().first()
        self.assertIsNotNone(sent_invoice.due_date)
        self.assertEqual(sent_invoice.total_price, 50)
        self.assertEquals(len(mail.outbox), 1)
        self.assertEquals(
            mail.outbox[0].subject,
            f"{invoice.title}'s Installment Invoice from {invoice.user.first_name} for {self.current_month}",
        )
        self.assertEquals(SentInvoice.objects.count(), 1)

    def test_send_installment_return_if_installments_all_sent(self):
        invoice = SingleInvoiceFactory(
            next_installment_date=timezone.now(), installments=2, balance_due=100
        )
        SentInvoiceFactory(invoice=invoice)
        SentInvoiceFactory(invoice=invoice)
        invoice_sent = send_invoice_installment(invoice.id)
        self.assertFalse(invoice_sent)
        self.assertEquals(len(mail.outbox), 0)
        self.assertEquals(SentInvoice.objects.count(), 2)

    def test_send_installment_renders_valid_items(self):
        invoice = SingleInvoiceFactory(
            next_installment_date=timezone.now(), installments=2, balance_due=100
        )
        line_item = LineItemFactory(invoice=invoice, quantity=1, unit_price=100)
        send_invoice_installment(invoice.id)
        invoice.refresh_from_db()
        sent_invoice = invoice.get_sent_invoice().first()
        sent_invoice.refresh_from_db()
        html_body = self.extract_html()
        sent_invoice_due_date = timezone.now() + timezone.timedelta(days=14)
        self.assertInHTML(
            f"""
            <div>
                <strong>Due By: </strong>
                {template_date(sent_invoice_due_date, "M. j, Y")}
            </div>
        """,
            html_body,
        )
        self.assertInHTML(
            f"""
            <div>{line_item.description}</div>
            <div>$50</div>
        """,
            html_body,
        )
        self.assertInHTML(
            """
            <div class="ml-24">$55</div>
            """,
            html_body,
        )


class TestWeeklyInvoiceUpdates(TestCase):
    @classmethod
    def extract_html(cls):
        s = mail.outbox[0].message().as_string()
        start = s.find("<body>") + len("<body>")
        end = s.find("</body>")
        message = s[start:end]
        return message

    def test_dont_send_weekly_update_if_no_active_subscription(self):
        invoice = IntervalInvoiceFactory()
        invoice.user.stripe_subscription_status = 3
        invoice.user.save()
        HoursLineItemFactory(invoice=invoice)

        send_weekly_updates()

        self.assertEquals(len(mail.outbox), 0)

    def test_dont_send_weekly_update_if_no_active_invoices(self):
        IntervalInvoiceFactory(is_paused=True)
        send_weekly_updates()

        self.assertEquals(len(mail.outbox), 0)

    def test_dont_send_weekly_update_if_no_non_archived_invoices(self):
        IntervalInvoiceFactory(is_archived=True)
        send_weekly_updates()

        self.assertEquals(len(mail.outbox), 0)

    @patch("timary.tasks.timezone")
    def test_dont_send_weekly_update_if_no_hours_logged(self, today_mock):
        todays_date = datetime(
            2023, 1, 20, 12, 30, 0, tzinfo=zoneinfo.ZoneInfo("America/New_York")
        )
        today_mock.now.return_value = todays_date
        IntervalInvoiceFactory()
        send_weekly_updates()
        self.assertEquals(len(mail.outbox), 0)

    @patch("timary.tasks.timezone")
    def test_send_weekly_update(self, today_mock):
        """Only shows hours tracked for current week, not prior and send email update."""
        todays_date = datetime(
            2023, 1, 20, 12, 30, 0, tzinfo=zoneinfo.ZoneInfo("America/New_York")
        )
        today_mock.now.return_value = todays_date
        invoice = IntervalInvoiceFactory(
            last_date=(todays_date - timedelta(days=3)).astimezone(
                tz=zoneinfo.ZoneInfo("America/New_York")
            ),
            total_budget=1000,
        )
        hour = HoursLineItemFactory(
            invoice=invoice,
            date_tracked=(todays_date - timedelta(days=1)).astimezone(
                tz=zoneinfo.ZoneInfo("America/New_York")
            ),
        )
        HoursLineItemFactory(
            invoice=invoice,
            date_tracked=(todays_date - timedelta(days=8)).astimezone(
                tz=zoneinfo.ZoneInfo("America/New_York")
            ),
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
                <div>${ floatformat(hour.quantity * invoice.rate, -2) }</div>
                """
            self.assertInHTML(msg, html_message)

        with self.subTest("Test budget appears in weekly update"):
            self.assertIn("Invoice Budget", html_message)
