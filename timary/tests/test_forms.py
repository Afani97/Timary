import uuid
import zoneinfo

from dateutil.relativedelta import relativedelta
from django.test import TestCase
from django.utils import timezone

from timary.forms import (
    CreateIntervalForm,
    CreateMilestoneForm,
    CreateWeeklyForm,
    HoursLineItemForm,
    InvoiceBrandingSettingsForm,
    LoginForm,
    PayInvoiceForm,
    RegisterForm,
    SingleInvoiceForm,
    SMSSettingsForm,
    UserForm,
)
from timary.tests.factories import (
    IntervalInvoiceFactory,
    InvoiceFactory,
    MilestoneInvoiceFactory,
    SentInvoiceFactory,
    UserFactory,
)
from timary.utils import get_starting_week_from_date


class TestLogin(TestCase):
    def test_login_success(self):
        form = LoginForm(data={"email": "user@test.com", "password": "test"})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.errors, {})

    def test_login_error_empty_email(self):
        form = LoginForm(data={"password": "test"})

        self.assertEqual(form.errors, {"email": ["This field is required."]})

    def test_login_error_invalid_email(self):
        form = LoginForm(data={"email": "username", "password": "test"})

        self.assertEqual(form.errors, {"email": ["Enter a valid email address."]})

    def test_login_error_empty_password(self):
        form = LoginForm(data={"email": "user@test.com"})

        self.assertEqual(form.errors, {"password": ["This field is required."]})


class TestRegister(TestCase):
    def test_register_success(self):
        form = RegisterForm(
            data={
                "email": "user@test.com",
                "full_name": "User User",
                "password": "test",
            }
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(form.errors, {})

        user = form.save()
        self.assertEqual(user.email, "user@test.com")
        self.assertEqual(user.get_full_name(), "User User")
        self.assertEqual(
            user.phone_number_availability, ["Mon", "Tue", "Wed", "Thu", "Fri"]
        )

    def test_register_error_empty_email(self):
        form = RegisterForm(data={"full_name": "User User", "password": "test"})
        self.assertEqual(form.errors, {"email": ["This field is required."]})

    def test_register_email_already_registered(self):
        user = UserFactory()
        form = RegisterForm(
            data={
                "email": user.email,
                "full_name": "User User",
                "password": "test",
            }
        )

        self.assertEqual(
            form.errors,
            {
                "__all__": [
                    "We're having trouble creating your account. Please try again"
                ]
            },
        )

    def test_register_name_not_valid(self):
        form = RegisterForm(
            data={
                "email": "user@test.com",
                "full_name": "12345",
                "password": "test",
            }
        )

        self.assertEqual(form.errors, {"full_name": ["Only valid names allowed."]})

    def test_register_error_empty_password(self):
        form = RegisterForm(
            data={
                "email": "user@test.com",
                "full_name": "User",
            }
        )

        self.assertEqual(form.errors, {"password": ["This field is required."]})

    def test_register_empty_all_fields(self):
        form = RegisterForm(data={})

        self.assertEqual(
            form.errors,
            {
                "email": ["This field is required."],
                "full_name": ["This field is required."],
                "password": ["This field is required."],
            },
        )


class TestInvoices(TestCase):
    def test_invoice_success(self):
        form = CreateIntervalForm(
            data={
                "title": "Some title",
                "rate": 100,
                "invoice_interval": "M",
                "client_name": "John Smith",
                "client_email": "user@test.com",
            }
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(form.errors, {})

    def test_invoice_error_missing_title(self):
        form = CreateIntervalForm(
            data={
                "rate": 100,
                "invoice_interval": "M",
                "client_name": "John Smith",
                "client_email": "user@test.com",
            }
        )
        self.assertEqual(form.errors, {"title": ["This field is required."]})

    def test_invoice_error_missing_invoice_rate(self):
        form = CreateIntervalForm(
            data={
                "title": "Some title",
                "invoice_interval": "M",
                "client_name": "John Smith",
                "client_email": "user@test.com",
            }
        )

        self.assertEqual(form.errors, {"rate": ["This field is required."]})

    def test_invoice_error_invoice_rate_min_value(self):
        form = CreateIntervalForm(
            data={
                "title": "Some title",
                "rate": 0,
                "invoice_interval": "M",
                "client_name": "John Smith",
                "client_email": "user@test.com",
            }
        )

        self.assertEqual(
            form.errors,
            {"rate": ["Ensure this value is greater than or equal to 1."]},
        )

    def test_invoice_error_missing_invoice_interval(self):
        form = CreateIntervalForm(
            data={
                "title": "Some title",
                "rate": 100,
                "client_name": "John Smith",
                "client_email": "user@test.com",
            }
        )

        self.assertEqual(form.errors, {"invoice_interval": ["This field is required."]})

    def test_invoice_error_incorrect_invoice_interval(self):
        form = CreateIntervalForm(
            data={
                "title": "Some title",
                "rate": 100,
                "invoice_interval": "I",
                "client_name": "John Smith",
                "client_email": "user@test.com",
            }
        )
        self.assertEqual(
            form.errors,
            {
                "invoice_interval": [
                    "Select a valid choice. I is not one of the available choices."
                ]
            },
        )

    def test_invoice_error_missing_milestone_total_step(self):
        form = CreateMilestoneForm(
            data={
                "title": "Some title",
                "rate": 100,
                "client_name": "John Smith",
                "client_email": "user@test.com",
            }
        )

        self.assertEqual(
            form.errors,
            {"milestone_total_steps": ["This field is required."]},
        )

    def test_invoice_error_milestone_total_step_less_than_current_step(self):
        invoice = MilestoneInvoiceFactory(milestone_step=5)
        form = CreateMilestoneForm(
            instance=invoice,
            data={
                "title": "Some title",
                "rate": 100,
                "milestone_total_steps": 3,
                "client_name": "John Smith",
                "client_email": "user@test.com",
            },
        )

        self.assertEqual(
            form.errors,
            {
                "milestone_total_steps": [
                    "Cannot set milestone total steps to less than what is already completed"
                ]
            },
        )

    def test_invoice_error_missing_client_name(self):
        form = CreateIntervalForm(
            data={
                "title": "Some title",
                "rate": 100,
                "invoice_interval": "M",
                "client_email": "user@test.com",
            }
        )

        self.assertIn(
            "A client needs be entered or selected from list", str(form.errors)
        )

    def test_invoice_error_invalid_client_name(self):
        form = CreateIntervalForm(
            data={
                "title": "Some title",
                "rate": 100,
                "invoice_interval": "M",
                "client_name": "12345",
                "client_email": "user@test.com",
            }
        )

        self.assertIn("Only valid names allowed.", str(form.errors))

    def test_invoice_error_missing_client_email(self):
        form = CreateIntervalForm(
            data={
                "title": "Some title",
                "rate": 100,
                "invoice_interval": "M",
                "client_name": "John Smith",
            }
        )

        self.assertIn(
            "A client needs be entered or selected from list", str(form.errors)
        )

    def test_invoice_error_invalid_client_email(self):
        form = CreateIntervalForm(
            data={
                "title": "Some title",
                "rate": 100,
                "invoice_interval": "M",
                "client_name": "John Smith",
                "client_email": "user@test",
            }
        )

        self.assertIn("Enter a valid email address.", str(form.errors))

    def test_invoice_error_duplicate_title(self):
        user = UserFactory()
        invoice = InvoiceFactory(user=user)
        form = CreateIntervalForm(
            user=user,
            data={
                "title": invoice.title,
                "rate": 100,
                "invoice_interval": "M",
                "client_name": "John Smith",
                "client_email": "user@test.com",
            },
        )

        self.assertEqual(
            form.errors, {"title": ["Duplicate invoice title not allowed."]}
        )

    def test_invoice_error_title_begins_with_number(self):
        form = CreateIntervalForm(
            data={
                "title": "1Password dev",
                "rate": 100,
                "invoice_interval": "M",
                "client_name": "User Test",
                "client_email": "user@test.com",
            }
        )

        self.assertEqual(form.errors, {"title": ["Title cannot start with a number."]})

    def test_invoice_error_missing_weekly_rate(self):
        form = CreateWeeklyForm(
            data={
                "title": "Some title",
                "client_name": "John Smith",
                "client_email": "user@test.com",
            }
        )

        self.assertEqual(form.errors, {"rate": ["This field is required."]})

    def test_weekly_invoice_over_2000_a_week(self):
        form = CreateWeeklyForm(
            data={
                "title": "Some title",
                "rate": 2500,
                "client_name": "John Smith",
                "client_email": "user@test.com",
            }
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(form.errors, {})

    def test_single_invoice(self):
        form = SingleInvoiceForm(
            data={
                "title": "Some title",
                "client_name": "John Smith",
                "client_email": "user@test.com",
                "due_date": timezone.now().date() + timezone.timedelta(weeks=1),
            }
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(form.errors, {})

    def test_single_invoice_error_due_date_less_than_today(self):
        form = SingleInvoiceForm(
            data={
                "title": "Some title",
                "client_name": "John Smith",
                "client_email": "user@test.com",
                "due_date": timezone.now().date(),
            }
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors, {"due_date": ["Due date cannot be set prior to today."]}
        )

    def test_single_invoice_error_title_named_with_an_number(self):
        form = SingleInvoiceForm(
            data={
                "title": "2Some title",
                "client_name": "John Smith",
                "client_email": "user@test.com",
                "due_date": timezone.now().date() + timezone.timedelta(weeks=1),
            }
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors, {"title": ["Title cannot start with a number."]})


class TestPayInvoice(TestCase):
    def test_invoice_success(self):
        sent_invoice = SentInvoiceFactory()
        form = PayInvoiceForm(
            sent_invoice=sent_invoice,
            data={
                "email": sent_invoice.invoice.client_email,
                "first_name": sent_invoice.invoice.client_name,
            },
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(form.errors, {})

    def test_sent_invoice_error_wrong_email(self):
        sent_invoice = SentInvoiceFactory()
        form = PayInvoiceForm(
            sent_invoice=sent_invoice,
            data={
                "email": "test@test.com",
                "first_name": sent_invoice.invoice.client_name,
            },
        )
        self.assertEqual(
            form.errors,
            {"email": ["Unable to process payment, please enter correct details."]},
        )

    def test_sent_invoice_error_wrong_first_name(self):
        sent_invoice = SentInvoiceFactory()
        form = PayInvoiceForm(
            sent_invoice=sent_invoice,
            data={
                "email": sent_invoice.invoice.client_email,
                "first_name": "User User",
            },
        )
        self.assertEqual(
            form.errors,
            {
                "first_name": [
                    "Unable to process payment, please enter correct details."
                ]
            },
        )


class TestHoursLineItem(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.today = timezone.now()
        cls.invoice = IntervalInvoiceFactory()
        cls.timezone = zoneinfo.ZoneInfo("America/New_York")

    def test_hours_success(self):
        form = HoursLineItemForm(
            data={"quantity": 1, "invoice": self.invoice.id, "date_tracked": self.today}
        )
        self.assertEqual(form.errors, {})

    def test_hours_error_missing_hours(self):
        form = HoursLineItemForm(
            data={"invoice": self.invoice.id, "date_tracked": self.today}
        )
        self.assertEqual(form.errors, {"quantity": ["This field is required."]})

    def test_hours_error_invalid_hours(self):
        form = HoursLineItemForm(
            data={
                "quantity": -1,
                "invoice": self.invoice.id,
                "date_tracked": self.today,
            }
        )
        self.assertEqual(
            form.errors,
            {"quantity": ["Invalid hours logged. Please log between 0 and 24 hours"]},
        )

        form = HoursLineItemForm(
            data={
                "quantity": 25,
                "invoice": self.invoice.id,
                "date_tracked": self.today,
            },
        )
        self.assertEqual(
            form.errors,
            {"quantity": ["Invalid hours logged. Please log between 0 and 24 hours"]},
        )

    def test_hours_error_missing_date_tracked(self):
        form = HoursLineItemForm(data={"quantity": 1, "invoice": self.invoice.id})
        self.assertEqual(form.errors, {"date_tracked": ["This field is required."]})

    def test_hours_error_missing_invoice(self):
        form = HoursLineItemForm(data={"quantity": 1, "date_tracked": self.today})
        self.assertEqual(form.errors, {"invoice": ["This field is required."]})

    def test_hours_error_invalid_invoice(self):
        form = HoursLineItemForm(
            data={"quantity": 1, "invoice": uuid.uuid4(), "date_tracked": self.today}
        )
        self.assertEqual(
            form.errors,
            {
                "invoice": [
                    "Select a valid choice. That choice is not one of the available choices."
                ]
            },
        )

    def test_hours_with_user_and_1_invoice(self):
        user = UserFactory()
        user.invoices.add(self.invoice)
        form = HoursLineItemForm(
            data={
                "quantity": 1,
                "invoice": self.invoice.id,
                "date_tracked": self.today,
            },
            user=user,
        )
        self.assertQuerysetEqual(list(form.fields["invoice"].queryset), [self.invoice])

    def test_hours_with_user_and_associated_invoices(self):
        user = UserFactory()
        InvoiceFactory()
        inv_1 = InvoiceFactory(user=user)
        inv_2 = InvoiceFactory(user=user)

        form = HoursLineItemForm(
            data={
                "quantity": 1,
                "invoice": inv_1.id,
                "date_tracked": self.today,
            },
            user=user,
        )
        self.assertQuerysetEqual(list(form.fields["invoice"].queryset), [inv_1, inv_2])

    def test_hours_all_empty_fields(self):
        form = HoursLineItemForm(data={})
        self.assertEqual(
            form.errors,
            {
                "quantity": ["This field is required."],
                "invoice": ["This field is required."],
                "date_tracked": ["This field is required."],
            },
        )

    def test_clean_date_tracked(self):
        """Hours should only be tracked after invoice's last date and up to current date"""
        form = HoursLineItemForm(
            data={
                "quantity": 1,
                "invoice": self.invoice.id,
                "date_tracked": self.today - relativedelta(months=2),
            }
        )
        self.assertEqual(
            form.errors,
            {"__all__": ["Cannot set date since your last invoice's cutoff date."]},
        )

        form = HoursLineItemForm(
            data={
                "quantity": 1,
                "invoice": self.invoice.id,
                "date_tracked": self.today + timezone.timedelta(days=7),
            },
        )
        self.assertEqual(
            form.errors, {"date_tracked": ["Cannot set date into the future!"]}
        )

    def test_hours_repeating_daily(self):
        date_tracked = timezone.datetime(2022, 1, 5)
        invoice = IntervalInvoiceFactory(
            last_date=timezone.datetime(2022, 1, 4, tzinfo=self.timezone)
        )
        form = HoursLineItemForm(
            data={
                "quantity": 1,
                "invoice": invoice.id,
                "date_tracked": date_tracked,
                "repeating": True,
                "repeat_end_date": timezone.now() + timezone.timedelta(weeks=1),
                "repeat_interval_schedule": "d",
            }
        )
        self.assertEqual(form.errors, {})
        self.assertDictEqual(
            form.cleaned_data.get("recurring_logic"),
            {
                "type": "repeating",
                "interval": "d",
                "interval_days": [],
                "starting_week": get_starting_week_from_date(date_tracked).isoformat(),
                "end_date": (timezone.now() + timezone.timedelta(weeks=1))
                .date()
                .isoformat(),
            },
        )

    def test_hours_repeating_weekly(self):
        date_tracked = timezone.datetime(2022, 1, 5)
        invoice = IntervalInvoiceFactory(
            last_date=timezone.datetime(2022, 1, 4, tzinfo=self.timezone)
        )
        form = HoursLineItemForm(
            data={
                "quantity": 1,
                "invoice": invoice.id,
                "date_tracked": date_tracked,
                "repeating": True,
                "repeat_end_date": timezone.now() + timezone.timedelta(weeks=1),
                "repeat_interval_schedule": "w",
                "repeat_interval_days": ["mon", "tue"],
            }
        )
        self.assertEqual(form.errors, {})
        self.assertDictEqual(
            form.cleaned_data.get("recurring_logic"),
            {
                "type": "repeating",
                "interval": "w",
                "interval_days": ["mon", "tue"],
                "starting_week": get_starting_week_from_date(date_tracked).isoformat(),
                "end_date": (timezone.now() + timezone.timedelta(weeks=1))
                .date()
                .isoformat(),
            },
        )

    def test_hours_recurring_daily(self):
        date_tracked = timezone.datetime(2022, 1, 5)
        invoice = IntervalInvoiceFactory(
            last_date=timezone.datetime(2022, 1, 4, tzinfo=self.timezone)
        )
        form = HoursLineItemForm(
            data={
                "quantity": 1,
                "invoice": invoice.id,
                "date_tracked": date_tracked,
                "recurring": True,
                "repeat_interval_schedule": "d",
            }
        )
        self.assertEqual(form.errors, {})
        self.assertDictEqual(
            form.cleaned_data.get("recurring_logic"),
            {
                "type": "recurring",
                "interval": "d",
                "interval_days": [],
                "starting_week": get_starting_week_from_date(date_tracked).isoformat(),
            },
        )

    def test_hours_recurring_weekly(self):
        date_tracked = timezone.datetime(2022, 1, 5)
        invoice = IntervalInvoiceFactory(
            last_date=timezone.datetime(2022, 1, 4, tzinfo=self.timezone)
        )
        form = HoursLineItemForm(
            data={
                "quantity": 1,
                "invoice": invoice.id,
                "date_tracked": date_tracked,
                "recurring": True,
                "repeat_interval_schedule": "w",
                "repeat_interval_days": ["thu", "fri"],
            }
        )
        self.assertEqual(form.errors, {})
        self.assertDictEqual(
            form.cleaned_data.get("recurring_logic"),
            {
                "type": "recurring",
                "interval": "w",
                "interval_days": ["thu", "fri"],
                "starting_week": get_starting_week_from_date(date_tracked).isoformat(),
            },
        )

    def test_repeating_hours_cannot_set_both_true(self):
        form = HoursLineItemForm(
            data={
                "quantity": 1,
                "invoice": self.invoice.id,
                "date_tracked": self.today,
                "recurring": True,
                "repeating": True,
                "repeat_interval_schedule": "w",
                "repeat_interval_days": ["mon", "tue"],
            }
        )
        self.assertIn(
            "Cannot set repeating and recurring both to true.", str(form.errors)
        )

    def test_repeating_hours_needs_end_date(self):
        """Recurring goes on until invoice is archived"""
        form = HoursLineItemForm(
            data={
                "quantity": 1,
                "invoice": self.invoice.id,
                "date_tracked": self.today,
                "repeating": True,
            }
        )
        self.assertIn(
            "Cannot have a repeating hour without an end date.", str(form.errors)
        )

    def test_repeating_hours_needs_end_date_greater_than_today(self):
        form = HoursLineItemForm(
            data={
                "quantity": 1,
                "invoice": self.invoice.id,
                "date_tracked": self.today,
                "repeating": True,
                "repeat_end_date": timezone.now() - timezone.timedelta(weeks=1),
            }
        )
        self.assertIn("Cannot set repeat end date less than today.", str(form.errors))

    def test_repeating_weekly_or_biweekly_need_days_set(self):
        form = HoursLineItemForm(
            data={
                "quantity": 1,
                "invoice": self.invoice.id,
                "date_tracked": self.today,
                "recurring": True,
                "repeat_interval_schedule": "w",
            }
        )
        self.assertIn("Need specific days which to add hours to.", str(form.errors))

    def test_repeating_has_valid_starting_week(self):
        date_tracked = timezone.datetime(2022, 1, 5)
        invoice = IntervalInvoiceFactory(
            last_date=timezone.datetime(2022, 1, 4, tzinfo=self.timezone)
        )
        form = HoursLineItemForm(
            data={
                "quantity": 1,
                "invoice": invoice.id,
                "date_tracked": date_tracked,
                "recurring": True,
                "repeat_interval_schedule": "d",
            }
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(
            form.cleaned_data.get("recurring_logic")["starting_week"],
            get_starting_week_from_date(date_tracked).isoformat(),
        )

    def test_hours_repeating_daily_update_starting_week_if_created_saturday(self):
        invoice = IntervalInvoiceFactory(
            last_date=timezone.datetime(2022, 1, 6, tzinfo=self.timezone)
        )
        form = HoursLineItemForm(
            data={
                "quantity": 1,
                "invoice": invoice.id,
                "date_tracked": timezone.datetime(2022, 1, 8),  # Sat Jan 7, 2022
                "recurring": True,
                "repeat_interval_schedule": "d",
            }
        )
        self.assertEqual(form.errors, {})
        self.assertDictEqual(
            form.cleaned_data.get("recurring_logic"),
            {
                "type": "recurring",
                "interval": "d",
                "interval_days": [],
                "starting_week": get_starting_week_from_date(
                    timezone.datetime(2022, 1, 9)  # Sun Jan 8, 2022
                ).isoformat(),
            },
        )

    def test_hours_repeating_biweekly_update_starting_week_if_created_saturday(self):
        invoice = IntervalInvoiceFactory(
            last_date=timezone.datetime(2022, 1, 6, tzinfo=self.timezone)
        )
        form = HoursLineItemForm(
            data={
                "quantity": 1,
                "invoice": invoice.id,
                "date_tracked": timezone.datetime(2022, 1, 8),  # Sat Jan 7, 2022
                "recurring": True,
                "repeat_interval_schedule": "b",
                "repeat_interval_days": ["mon", "tue"],
            }
        )
        self.assertEqual(form.errors, {})
        self.assertDictEqual(
            form.cleaned_data.get("recurring_logic"),
            {
                "type": "recurring",
                "interval": "b",
                "interval_days": ["mon", "tue"],
                "starting_week": get_starting_week_from_date(
                    timezone.datetime(2022, 1, 16)  # Sun Jan 15, 2022
                ).isoformat(),
            },
        )


class TestUser(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory()
        cls.timezone = "America/New_York"

    def test_user_success(self):
        form = UserForm(
            data={
                "email": "user@test.com",
                "first_name": self.user.first_name,
                "last_name": self.user.last_name,
                "phone_number": "+17742613186",
                "timezone": self.timezone,
            }
        )
        self.assertEqual(form.errors, {})

    def test_user_missing_email_error(self):
        form = UserForm(
            data={
                "first_name": self.user.first_name,
                "last_name": self.user.last_name,
                "timezone": self.timezone,
            }
        )
        self.assertEqual(form.errors, {"email": ["This field is required."]})

    def test_user_missing_first_name_error(self):
        form = UserForm(
            data={
                "email": "user@test.com",
                "last_name": self.user.last_name,
                "timezone": self.timezone,
            }
        )
        self.assertEqual(form.errors, {"first_name": ["This field is required."]})

    def test_user_already_present_email_error(self):
        form = UserForm(
            data={
                "email": self.user.email,
                "first_name": self.user.first_name,
                "last_name": self.user.last_name,
                "timezone": self.timezone,
            }
        )
        self.assertEqual(form.errors, {"email": ["Email already registered!"]})

    def test_user_already_invalid_name_error(self):
        form = UserForm(
            data={
                "email": "user@test.com",
                "first_name": self.user.first_name + "123",
                "last_name": self.user.last_name,
                "timezone": self.timezone,
            }
        )
        self.assertEqual(form.errors, {"first_name": ["Only valid names allowed."]})

    def test_user_invalid_phone_number_error(self):
        form = UserForm(
            data={
                "email": "user@test.com",
                "first_name": self.user.first_name,
                "last_name": self.user.last_name,
                "phone_number": "abc123",
                "timezone": self.timezone,
            }
        )
        self.assertEqual(
            form.errors, {"phone_number": ["Wrong format, needs to be: +13334445555"]}
        )

    def test_user_missing_fields_error(self):
        form = UserForm(data={})
        self.assertEqual(
            form.errors,
            {
                "email": ["This field is required."],
                "first_name": ["This field is required."],
                "timezone": ["This field is required."],
            },
        )


class TestSettings(TestCase):
    def test_update_sms_settings(self):
        user = UserFactory()
        form = SMSSettingsForm(
            instance=user,
            data={"phone_number_availability": ["Mon", "Tue"]},
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(form.errors, {})
        form.save()
        user.refresh_from_db()
        self.assertEqual(user.phone_number_availability, ["Mon", "Tue"])

    def test_valid_invoice_branding_options(self):
        form = InvoiceBrandingSettingsForm(
            data={
                "due_date": "1",
                "company_name": "Awesome inc",
                "hide_timary": False,
                "show_profile_pic": True,
                "linked_in": "some_url",
                "twitter": "some_url",
                "youtube": "some_url",
            },
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(form.errors, {})
