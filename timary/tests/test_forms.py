import datetime
import uuid

from dateutil.relativedelta import relativedelta
from django.test import TestCase

from timary.forms import (
    CreateIntervalForm,
    CreateMilestoneForm,
    CreateWeeklyForm,
    DailyHoursForm,
    InvoiceBrandingSettingsForm,
    LoginForm,
    PayInvoiceForm,
    RegisterForm,
    SMSSettingsForm,
    UserForm,
)
from timary.tests.factories import InvoiceFactory, SentInvoiceFactory, UserFactory
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
                "invoice_rate": 100,
                "invoice_type": 1,
                "invoice_interval": "M",
                "email_recipient_name": "John Smith",
                "email_recipient": "user@test.com",
            }
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(form.errors, {})

    def test_invoice_error_missing_title(self):
        form = CreateIntervalForm(
            data={
                "invoice_rate": 100,
                "invoice_type": 1,
                "invoice_interval": "M",
                "email_recipient_name": "John Smith",
                "email_recipient": "user@test.com",
            }
        )
        self.assertEqual(form.errors, {"title": ["This field is required."]})

    def test_invoice_error_missing_invoice_rate(self):
        form = CreateIntervalForm(
            data={
                "title": "Some title",
                "invoice_type": 1,
                "invoice_interval": "M",
                "email_recipient_name": "John Smith",
                "email_recipient": "user@test.com",
            }
        )

        self.assertEqual(form.errors, {"invoice_rate": ["This field is required."]})

    def test_invoice_error_invoice_rate_min_value(self):
        form = CreateIntervalForm(
            data={
                "title": "Some title",
                "invoice_rate": 0,
                "invoice_type": 1,
                "invoice_interval": "M",
                "email_recipient_name": "John Smith",
                "email_recipient": "user@test.com",
            }
        )

        self.assertEqual(
            form.errors,
            {"invoice_rate": ["Ensure this value is greater than or equal to 1."]},
        )

    def test_invoice_error_missing_invoice_interval(self):
        form = CreateIntervalForm(
            data={
                "title": "Some title",
                "invoice_rate": 100,
                "invoice_type": 1,
                "email_recipient_name": "John Smith",
                "email_recipient": "user@test.com",
            }
        )

        self.assertEqual(form.errors, {"invoice_interval": ["This field is required."]})

    def test_invoice_error_incorrect_invoice_interval(self):
        form = CreateIntervalForm(
            data={
                "title": "Some title",
                "invoice_rate": 100,
                "invoice_type": 1,
                "invoice_interval": "I",
                "email_recipient_name": "John Smith",
                "email_recipient": "user@test.com",
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
                "invoice_rate": 100,
                "invoice_type": 2,
                "email_recipient_name": "John Smith",
                "email_recipient": "user@test.com",
            }
        )

        self.assertEqual(
            form.errors,
            {"milestone_total_steps": ["This field is required."]},
        )

    def test_invoice_error_milestone_total_step_less_than_current_step(self):
        invoice = InvoiceFactory(invoice_type=2, milestone_step=5)
        form = CreateMilestoneForm(
            instance=invoice,
            data={
                "title": "Some title",
                "invoice_rate": 100,
                "invoice_type": 2,
                "milestone_total_steps": 3,
                "email_recipient_name": "John Smith",
                "email_recipient": "user@test.com",
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

    def test_invoice_error_missing_email_recipient_name(self):
        form = CreateIntervalForm(
            data={
                "title": "Some title",
                "invoice_rate": 100,
                "invoice_type": 1,
                "invoice_interval": "M",
                "email_recipient": "user@test.com",
            }
        )

        self.assertIn(
            "A client needs be entered or selected from list", str(form.errors)
        )

    def test_invoice_error_invalid_email_recipient_name(self):
        form = CreateIntervalForm(
            data={
                "title": "Some title",
                "invoice_rate": 100,
                "invoice_type": 1,
                "invoice_interval": "M",
                "email_recipient_name": "12345",
                "email_recipient": "user@test.com",
            }
        )

        self.assertIn("Only valid names allowed.", str(form.errors))

    def test_invoice_error_missing_email_recipient(self):
        form = CreateIntervalForm(
            data={
                "title": "Some title",
                "invoice_rate": 100,
                "invoice_type": 1,
                "invoice_interval": "M",
                "email_recipient_name": "John Smith",
            }
        )

        self.assertIn(
            "A client needs be entered or selected from list", str(form.errors)
        )

    def test_invoice_error_invalid_email_recipient(self):
        form = CreateIntervalForm(
            data={
                "title": "Some title",
                "invoice_rate": 100,
                "invoice_type": 1,
                "invoice_interval": "M",
                "email_recipient_name": "John Smith",
                "email_recipient": "user@test",
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
                "invoice_rate": 100,
                "invoice_type": 1,
                "invoice_interval": "M",
                "email_recipient_name": "John Smith",
                "email_recipient": "user@test.com",
            },
        )

        self.assertEqual(
            form.errors, {"title": ["Duplicate invoice title not allowed."]}
        )

    def test_invoice_error_title_begins_with_number(self):
        form = CreateIntervalForm(
            data={
                "title": "1Password dev",
                "invoice_rate": 100,
                "invoice_type": 1,
                "invoice_interval": "M",
                "email_recipient_name": "User Test",
                "email_recipient": "user@test.com",
            }
        )

        self.assertEqual(form.errors, {"title": ["Title cannot start with a number."]})

    def test_invoice_error_missing_weekly_rate(self):
        form = CreateWeeklyForm(
            data={
                "title": "Some title",
                "invoice_type": 3,
                "email_recipient_name": "John Smith",
                "email_recipient": "user@test.com",
            }
        )

        self.assertEqual(form.errors, {"invoice_rate": ["This field is required."]})


class TestPayInvoice(TestCase):
    def test_invoice_success(self):
        sent_invoice = SentInvoiceFactory()
        form = PayInvoiceForm(
            sent_invoice=sent_invoice,
            data={
                "email": sent_invoice.invoice.email_recipient,
                "first_name": sent_invoice.invoice.email_recipient_name,
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
                "first_name": sent_invoice.invoice.email_recipient_name,
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
                "email": sent_invoice.invoice.email_recipient,
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


class TestDailyHours(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.today = datetime.date.today()
        cls.invoice = InvoiceFactory()

    def test_hours_success(self):
        form = DailyHoursForm(
            data={"hours": 1, "invoice": self.invoice.id, "date_tracked": self.today}
        )
        self.assertEqual(form.errors, {})

    def test_hours_error_missing_hours(self):
        form = DailyHoursForm(
            data={"invoice": self.invoice.id, "date_tracked": self.today}
        )
        self.assertEqual(form.errors, {"hours": ["This field is required."]})

    def test_hours_error_invalid_hours(self):
        form = DailyHoursForm(
            data={"hours": -1, "invoice": self.invoice.id, "date_tracked": self.today}
        )
        self.assertEqual(
            form.errors,
            {"hours": ["Invalid hours logged. Please log between 0 and 24 hours"]},
        )

        form = DailyHoursForm(
            data={"hours": 25, "invoice": self.invoice.id, "date_tracked": self.today},
        )
        self.assertEqual(
            form.errors,
            {"hours": ["Invalid hours logged. Please log between 0 and 24 hours"]},
        )

    def test_hours_error_missing_date_tracked(self):
        form = DailyHoursForm(data={"hours": 1, "invoice": self.invoice.id})
        self.assertEqual(form.errors, {"date_tracked": ["This field is required."]})

    def test_hours_error_missing_invoice(self):
        form = DailyHoursForm(data={"hours": 1, "date_tracked": self.today})
        self.assertEqual(form.errors, {"invoice": ["This field is required."]})

    def test_hours_error_invalid_invoice(self):
        form = DailyHoursForm(
            data={"hours": 1, "invoice": uuid.uuid4(), "date_tracked": self.today}
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
        form = DailyHoursForm(
            data={
                "hours": 1,
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

        form = DailyHoursForm(
            data={
                "hours": 1,
                "invoice": inv_1.id,
                "date_tracked": self.today,
            },
            user=user,
        )
        self.assertQuerysetEqual(list(form.fields["invoice"].queryset), [inv_1, inv_2])

    def test_hours_all_empty_fields(self):
        form = DailyHoursForm(data={})
        self.assertEqual(
            form.errors,
            {
                "hours": ["This field is required."],
                "invoice": ["This field is required."],
                "date_tracked": ["This field is required."],
            },
        )

    def test_clean_date_tracked(self):
        """Hours should only be tracked after invoice's last date and up to current date"""
        form = DailyHoursForm(
            data={
                "hours": 1,
                "invoice": self.invoice.id,
                "date_tracked": self.today - relativedelta(months=2),
            }
        )
        self.assertEqual(
            form.errors,
            {"__all__": ["Cannot set date since your last invoice's cutoff date."]},
        )

        form = DailyHoursForm(
            data={
                "hours": 1,
                "invoice": self.invoice.id,
                "date_tracked": self.today + datetime.timedelta(days=7),
            },
        )
        self.assertEqual(
            form.errors, {"date_tracked": ["Cannot set date into the future!"]}
        )

    def test_hours_repeating_daily(self):
        form = DailyHoursForm(
            data={
                "hours": 1,
                "invoice": self.invoice.id,
                "date_tracked": self.today,
                "repeating": True,
                "repeat_end_date": datetime.date.today() + datetime.timedelta(weeks=1),
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
                "starting_week": "2022-12-25",
                "end_date": "2023-01-05",
            },
        )

    def test_hours_repeating_weekly(self):
        form = DailyHoursForm(
            data={
                "hours": 1,
                "invoice": self.invoice.id,
                "date_tracked": self.today,
                "repeating": True,
                "repeat_end_date": datetime.date.today() + datetime.timedelta(weeks=1),
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
                "starting_week": "2022-12-25",
                "end_date": "2023-01-05",
            },
        )

    def test_hours_recurring_daily(self):
        form = DailyHoursForm(
            data={
                "hours": 1,
                "invoice": self.invoice.id,
                "date_tracked": self.today,
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
                "starting_week": "2022-12-25",
            },
        )

    def test_hours_recurring_weekly(self):
        form = DailyHoursForm(
            data={
                "hours": 1,
                "invoice": self.invoice.id,
                "date_tracked": self.today,
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
                "starting_week": "2022-12-25",
            },
        )

    def test_repeating_hours_cannot_set_both_true(self):
        form = DailyHoursForm(
            data={
                "hours": 1,
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
        form = DailyHoursForm(
            data={
                "hours": 1,
                "invoice": self.invoice.id,
                "date_tracked": self.today,
                "repeating": True,
            }
        )
        self.assertIn(
            "Cannot have a repeating hour without an end date.", str(form.errors)
        )

    def test_repeating_hours_needs_end_date_greater_than_today(self):
        form = DailyHoursForm(
            data={
                "hours": 1,
                "invoice": self.invoice.id,
                "date_tracked": self.today,
                "repeating": True,
                "repeat_end_date": datetime.date.today() - datetime.timedelta(weeks=1),
            }
        )
        self.assertIn("Cannot set repeat end date less than today.", str(form.errors))

    def test_repeating_weekly_or_biweekly_need_days_set(self):
        form = DailyHoursForm(
            data={
                "hours": 1,
                "invoice": self.invoice.id,
                "date_tracked": self.today,
                "recurring": True,
                "repeat_interval_schedule": "w",
            }
        )
        self.assertIn("Need specific days which to add hours to.", str(form.errors))

    def test_repeating_has_valid_starting_week(self):
        form = DailyHoursForm(
            data={
                "hours": 1,
                "invoice": self.invoice.id,
                "date_tracked": self.today,
                "recurring": True,
                "repeat_interval_schedule": "d",
            }
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(
            form.cleaned_data.get("recurring_logic")["starting_week"],
            get_starting_week_from_date(datetime.date.today()).isoformat(),
        )


class TestUser(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory()

    def test_user_success(self):
        form = UserForm(
            data={
                "email": "user@test.com",
                "first_name": self.user.first_name,
                "last_name": self.user.last_name,
                "phone_number": "+17742613186",
            }
        )
        self.assertEqual(form.errors, {})

    def test_user_missing_email_error(self):
        form = UserForm(
            data={
                "first_name": self.user.first_name,
                "last_name": self.user.last_name,
            }
        )
        self.assertEqual(form.errors, {"email": ["This field is required."]})

    def test_user_missing_first_name_error(self):
        form = UserForm(
            data={
                "email": "user@test.com",
                "last_name": self.user.last_name,
            }
        )
        self.assertEqual(form.errors, {"first_name": ["This field is required."]})

    def test_user_already_present_email_error(self):
        form = UserForm(
            data={
                "email": self.user.email,
                "first_name": self.user.first_name,
                "last_name": self.user.last_name,
            }
        )
        self.assertEqual(form.errors, {"email": ["Email already registered!"]})

    def test_user_already_invalid_name_error(self):
        form = UserForm(
            data={
                "email": "user@test.com",
                "first_name": self.user.first_name + "123",
                "last_name": self.user.last_name,
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
