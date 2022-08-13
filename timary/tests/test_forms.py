import datetime
import uuid

from dateutil.relativedelta import relativedelta
from django.test import TestCase

from timary.forms import (
    DailyHoursForm,
    InvoiceBrandingSettingsForm,
    InvoiceForm,
    LoginForm,
    MembershipTierSettingsForm,
    PayInvoiceForm,
    RegisterForm,
    SMSSettingsForm,
    UserForm,
)
from timary.models import User
from timary.tests.factories import InvoiceFactory, SentInvoiceFactory, UserFactory


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
                "membership_tier": "19",
            }
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(form.errors, {})

        user = form.save()
        self.assertEqual(user.email, "user@test.com")
        self.assertEqual(user.get_full_name(), "User User")
        self.assertEqual(user.membership_tier, User.MembershipTier.PROFESSIONAL)
        self.assertEqual(
            user.phone_number_availability, ["Mon", "Tue", "Wed", "Thu", "Fri"]
        )

    def test_register_error_empty_email(self):
        form = RegisterForm(
            data={"full_name": "User User", "password": "test", "membership_tier": "19"}
        )
        self.assertEqual(form.errors, {"email": ["This field is required."]})

    def test_register_email_already_registered(self):
        user = UserFactory()
        form = RegisterForm(
            data={
                "email": user.email,
                "full_name": "User User",
                "password": "test",
                "membership_tier": "19",
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
                "membership_tier": "19",
            }
        )

        self.assertEqual(form.errors, {"full_name": ["Only valid names allowed."]})

    def test_register_error_empty_password(self):
        form = RegisterForm(
            data={
                "email": "user@test.com",
                "full_name": "User",
                "membership_tier": "19",
            }
        )

        self.assertEqual(form.errors, {"password": ["This field is required."]})

    def test_register_error_empty_membership_tier(self):
        form = RegisterForm(
            data={
                "email": "user@test.com",
                "full_name": "User User",
                "password": "test",
            }
        )

        self.assertEqual(form.errors, {"membership_tier": ["This field is required."]})

    def test_register_empty_all_fields(self):
        form = RegisterForm(data={})

        self.assertEqual(
            form.errors,
            {
                "email": ["This field is required."],
                "full_name": ["This field is required."],
                "password": ["This field is required."],
                "membership_tier": ["This field is required."],
            },
        )


class TestInvoice(TestCase):
    def test_invoice_success(self):
        form = InvoiceForm(
            data={
                "title": "Some title",
                "hourly_rate": 100,
                "invoice_type": 1,
                "invoice_interval": "M",
                "milestone_total_steps": 2,
                "email_recipient_name": "John Smith",
                "email_recipient": "user@test.com",
            }
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(form.errors, {})

    def test_invoice_error_missing_title(self):
        form = InvoiceForm(
            data={
                "hourly_rate": 100,
                "invoice_type": 1,
                "invoice_interval": "M",
                "milestone_total_steps": 2,
                "email_recipient_name": "John Smith",
                "email_recipient": "user@test.com",
            }
        )
        self.assertEqual(form.errors, {"title": ["This field is required."]})

    def test_invoice_error_missing_hourly_rate(self):
        form = InvoiceForm(
            data={
                "title": "Some title",
                "invoice_type": 1,
                "invoice_interval": "M",
                "milestone_total_steps": 2,
                "email_recipient_name": "John Smith",
                "email_recipient": "user@test.com",
            }
        )

        self.assertEqual(form.errors, {"hourly_rate": ["This field is required."]})

    def test_invoice_error_hourly_rate_min_value(self):
        form = InvoiceForm(
            data={
                "title": "Some title",
                "hourly_rate": 0,
                "invoice_type": 1,
                "invoice_interval": "M",
                "milestone_total_steps": 2,
                "email_recipient_name": "John Smith",
                "email_recipient": "user@test.com",
            }
        )

        self.assertEqual(
            form.errors,
            {"hourly_rate": ["Ensure this value is greater than or equal to 1."]},
        )

    def test_invoice_error_missing_invoice_interval(self):
        form = InvoiceForm(
            data={
                "title": "Some title",
                "hourly_rate": 100,
                "invoice_type": 1,
                "email_recipient_name": "John Smith",
                "email_recipient": "user@test.com",
            }
        )

        self.assertEqual(
            form.errors, {"invoice_interval": ["Invoice interval is required"]}
        )

    def test_invoice_error_incorrect_invoice_interval(self):
        form = InvoiceForm(
            data={
                "title": "Some title",
                "hourly_rate": 100,
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
                    "Select a valid choice. I is not one of the available choices.",
                    "Invoice interval is required",
                ]
            },
        )

    def test_invoice_error_missing_milestone_total_step(self):
        form = InvoiceForm(
            data={
                "title": "Some title",
                "hourly_rate": 100,
                "invoice_type": 2,
                "email_recipient_name": "John Smith",
                "email_recipient": "user@test.com",
            }
        )

        self.assertEqual(
            form.errors,
            {"milestone_total_steps": ["Milestone total steps is required"]},
        )

    def test_invoice_error_milestone_total_step_less_than_current_step(self):
        invoice = InvoiceFactory(invoice_type=2, milestone_step=5)
        form = InvoiceForm(
            instance=invoice,
            data={
                "title": "Some title",
                "hourly_rate": 100,
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
        form = InvoiceForm(
            data={
                "title": "Some title",
                "hourly_rate": 100,
                "invoice_type": 1,
                "invoice_interval": "M",
                "email_recipient": "user@test.com",
            }
        )

        self.assertEqual(
            form.errors, {"email_recipient_name": ["This field is required."]}
        )

    def test_invoice_error_invalid_email_recipient_name(self):
        form = InvoiceForm(
            data={
                "title": "Some title",
                "hourly_rate": 100,
                "invoice_type": 1,
                "invoice_interval": "M",
                "email_recipient_name": "12345",
                "email_recipient": "user@test.com",
            }
        )

        self.assertEqual(
            form.errors, {"email_recipient_name": ["Only valid names allowed."]}
        )

    def test_invoice_error_missing_email_recipient(self):
        form = InvoiceForm(
            data={
                "title": "Some title",
                "hourly_rate": 100,
                "invoice_type": 1,
                "invoice_interval": "M",
                "email_recipient_name": "John Smith",
            }
        )

        self.assertEqual(form.errors, {"email_recipient": ["This field is required."]})

    def test_invoice_error_invalid_email_recipient(self):
        form = InvoiceForm(
            data={
                "title": "Some title",
                "hourly_rate": 100,
                "invoice_type": 1,
                "invoice_interval": "M",
                "email_recipient_name": "John Smith",
                "email_recipient": "user@test",
            }
        )

        self.assertEqual(
            form.errors, {"email_recipient": ["Enter a valid email address."]}
        )

    def test_invoice_error_duplicate_title(self):
        user = UserFactory()
        invoice = InvoiceFactory(user=user)
        form = InvoiceForm(
            user=user,
            data={
                "title": invoice.title,
                "hourly_rate": 100,
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
        form = InvoiceForm(
            data={
                "title": "1Password dev",
                "hourly_rate": 100,
                "invoice_type": 1,
                "invoice_interval": "M",
                "email_recipient_name": "User Test",
                "email_recipient": "user@test.com",
            }
        )

        self.assertEqual(form.errors, {"title": ["Title cannot start with a number."]})


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
            form.errors, {"email": ["Wrong email recipient, unable to process payment"]}
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
            {"first_name": ["Wrong name recipient, unable to process payment"]},
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

    def test_update_membership_tier_settings_errors(self):
        user = UserFactory()
        form = MembershipTierSettingsForm(
            instance=user,
            data={"membership_tier": "5"},
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(form.errors, {})
        form.save()
        user.refresh_from_db()
        self.assertEqual(user.membership_tier, 5)

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
