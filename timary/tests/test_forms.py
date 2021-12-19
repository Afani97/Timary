import datetime
import uuid

from django.test import TestCase

from timary.forms import DailyHoursForm, InvoiceForm, LoginForm, RegisterForm, UserForm
from timary.tests.factories import InvoiceFactory, UserFactory


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
            data={"email": "user@test.com", "first_name": "User", "password": "test"}
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(form.errors, {})

    def test_register_error_empty_email(self):
        form = RegisterForm(data={"first_name": "User", "password": "test"})
        self.assertEqual(form.errors, {"email": ["This field is required."]})

    def test_register_email_already_registered(self):
        user = UserFactory()
        form = RegisterForm(
            data={"email": user.email, "first_name": "User", "password": "test"}
        )

        self.assertEqual(form.errors, {"email": ["Email already registered!"]})

    def test_register_name_not_valid(self):
        form = RegisterForm(
            data={"email": "user@test.com", "first_name": "12345", "password": "test"}
        )

        self.assertEqual(form.errors, {"first_name": ["Only valid names allowed."]})

    def test_register_error_empty_password(self):
        form = RegisterForm(data={"email": "user@test.com", "first_name": "User"})

        self.assertEqual(form.errors, {"password": ["This field is required."]})

    def test_register_empty_all_fields(self):
        form = RegisterForm(data={})

        self.assertEqual(
            form.errors,
            {
                "email": ["This field is required."],
                "first_name": ["This field is required."],
                "password": ["This field is required."],
            },
        )


class TestInvoice(TestCase):
    def test_invoice_success(self):
        form = InvoiceForm(
            data={
                "title": "Some title",
                "hourly_rate": 100,
                "invoice_interval": "M",
                "email_recipient_name": "User",
                "email_recipient": "user@test.com",
            }
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(form.errors, {})

    def test_invoice_error_missing_title(self):
        form = InvoiceForm(
            data={
                "hourly_rate": 100,
                "invoice_interval": "M",
                "email_recipient_name": "User",
                "email_recipient": "user@test.com",
            }
        )
        self.assertEqual(form.errors, {"title": ["This field is required."]})

    def test_invoice_error_missing_hourly_rate(self):
        form = InvoiceForm(
            data={
                "title": "Some title",
                "invoice_interval": "M",
                "email_recipient_name": "User",
                "email_recipient": "user@test.com",
            }
        )

        self.assertEqual(form.errors, {"hourly_rate": ["This field is required."]})

    def test_invoice_error_hourly_rate_min_value(self):
        form = InvoiceForm(
            data={
                "title": "Some title",
                "hourly_rate": 0,
                "invoice_interval": "M",
                "email_recipient_name": "User",
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
                "email_recipient_name": "User",
                "email_recipient": "user@test.com",
            }
        )

        self.assertEqual(form.errors, {"invoice_interval": ["This field is required."]})

    def test_invoice_error_incorrect_invoice_interval(self):
        form = InvoiceForm(
            data={
                "title": "Some title",
                "hourly_rate": 100,
                "invoice_interval": "I",
                "email_recipient_name": "User",
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

    def test_invoice_error_missing_email_recipient_name(self):
        form = InvoiceForm(
            data={
                "title": "Some title",
                "hourly_rate": 100,
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
                "invoice_interval": "M",
                "email_recipient_name": "User",
            }
        )

        self.assertEqual(form.errors, {"email_recipient": ["This field is required."]})

    def test_invoice_error_invalid_email_recipient(self):
        form = InvoiceForm(
            data={
                "title": "Some title",
                "hourly_rate": 100,
                "invoice_interval": "M",
                "email_recipient_name": "User",
                "email_recipient": "user@test",
            }
        )

        self.assertEqual(
            form.errors, {"email_recipient": ["Enter a valid email address."]}
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
        self.assertEqual(form.errors, {"hours": ["-1 cannot be less than 0 hours"]})

        form = DailyHoursForm(
            data={"hours": 25, "invoice": self.invoice.id, "date_tracked": self.today}
        )
        self.assertEqual(form.errors, {"hours": ["25 cannot be greater than 24 hours"]})

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
