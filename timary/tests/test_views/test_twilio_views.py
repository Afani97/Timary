import datetime
from dataclasses import dataclass
from unittest.mock import patch

from django.db.models import Sum
from django.test import TestCase
from django.test.client import RequestFactory
from django.test.utils import override_settings
from django.urls import reverse
from django_twilio.decorators import twilio_view

from timary.models import DailyHoursInput
from timary.tasks import send_reminder_sms
from timary.tests.factories import InvoiceFactory, UserFactory
from timary.views.twilio_views import twilio_reply


class TestTwilioSendReminderSMS(TestCase):
    @patch("twilio.rest.api.v2010.account.message.MessageList.create")
    @patch("timary.tasks.date")
    def test_send_0_messages(self, today_mock, message_create_mock):
        today_mock.today.return_value = datetime.date(2022, 1, 10)
        today_mock.side_effect = lambda *args, **kw: datetime.date(*args, **kw)
        message_create_mock.return_value = None

        invoices_sent = send_reminder_sms()
        self.assertEqual("0 message(s) sent.", invoices_sent)

    @patch("twilio.rest.api.v2010.account.message.MessageList.create")
    @patch("timary.tasks.date")
    def test_send_1_message(self, today_mock, message_create_mock):
        today_mock.today.return_value = datetime.date(2022, 1, 10)
        today_mock.side_effect = lambda *args, **kw: datetime.date(*args, **kw)
        message_create_mock.return_value = None

        InvoiceFactory(user__phone_number_availability=["Mon"])

        invoices_sent = send_reminder_sms()
        self.assertEqual("1 message(s) sent.", invoices_sent)

    @patch("twilio.rest.api.v2010.account.message.MessageList.create")
    def test_send_1_message_as_starter(self, message_create_mock):
        message_create_mock.return_value = None

        InvoiceFactory(user__membership_tier=5)

        invoices_sent = send_reminder_sms()
        self.assertEqual("0 message(s) sent.", invoices_sent)

    @patch("twilio.rest.api.v2010.account.message.MessageList.create")
    @patch("timary.tasks.date")
    def test_send_1_message_as_business(self, today_mock, message_create_mock):
        today_mock.today.return_value = datetime.date(2022, 1, 10)
        today_mock.side_effect = lambda *args, **kw: datetime.date(*args, **kw)
        message_create_mock.return_value = None

        InvoiceFactory(
            user__membership_tier=49, user__phone_number_availability=["Mon"]
        )

        invoices_sent = send_reminder_sms()
        self.assertEqual("1 message(s) sent.", invoices_sent)

    @patch("twilio.rest.api.v2010.account.message.MessageList.create")
    @patch("timary.tasks.date")
    def test_send_3_messages(self, today_mock, message_create_mock):
        today_mock.today.return_value = datetime.date(2022, 1, 10)
        today_mock.side_effect = lambda *args, **kw: datetime.date(*args, **kw)
        message_create_mock.return_value = None

        InvoiceFactory(user__phone_number_availability=["Mon"])
        InvoiceFactory(user__phone_number_availability=["Mon"])
        InvoiceFactory(user__phone_number_availability=["Mon"])

        invoices_sent = send_reminder_sms()
        self.assertEqual("3 message(s) sent.", invoices_sent)

    @patch("twilio.rest.api.v2010.account.message.MessageList.create")
    @patch("timary.tasks.date")
    def test_send_1_message_filtering_users(self, today_mock, message_create_mock):
        today_mock.today.return_value = datetime.date(2022, 1, 10)
        today_mock.side_effect = lambda *args, **kw: datetime.date(*args, **kw)
        message_create_mock.return_value = None

        InvoiceFactory(user__phone_number=None)
        InvoiceFactory(user__phone_number="")
        InvoiceFactory(next_date=None)
        InvoiceFactory(user__phone_number_availability=["Mon"])

        invoices_sent = send_reminder_sms()
        self.assertEqual("1 message(s) sent.", invoices_sent)

    @patch("twilio.rest.api.v2010.account.message.MessageList.create")
    @patch("timary.tasks.date")
    def test_send_1_message_from_1_user_with_2_invoices(
        self, today_mock, message_create_mock
    ):
        today_mock.today.return_value = datetime.date(2022, 1, 10)
        today_mock.side_effect = lambda *args, **kw: datetime.date(*args, **kw)
        message_create_mock.return_value = None

        user = UserFactory(phone_number_availability=["Mon"])

        InvoiceFactory(user=user)
        InvoiceFactory(user=user)

        invoices_sent = send_reminder_sms()
        self.assertEqual("1 message(s) sent.", invoices_sent)

    @patch("twilio.rest.api.v2010.account.message.MessageList.create")
    @patch("timary.tasks.date")
    def test_does_not_send_1_message_on_off_day(self, today_mock, message_create_mock):
        today_mock.today.return_value = datetime.date(2022, 1, 10)
        today_mock.side_effect = lambda *args, **kw: datetime.date(*args, **kw)
        message_create_mock.return_value = None

        InvoiceFactory(user__phone_number_availability=["Tue"])

        invoices_sent = send_reminder_sms()
        self.assertEqual("0 message(s) sent.", invoices_sent)

    @patch("twilio.rest.api.v2010.account.message.MessageList.create")
    @patch("timary.tasks.date")
    def test_do_not_send_1_message_in_between(self, today_mock, message_create_mock):
        today_mock.today.return_value = datetime.date(2022, 1, 10)
        today_mock.side_effect = lambda *args, **kw: datetime.date(*args, **kw)
        message_create_mock.return_value = None

        InvoiceFactory(user__phone_number_availability=["Sun", "Tue"])

        invoices_sent = send_reminder_sms()
        self.assertEqual("0 message(s) sent.", invoices_sent)


@dataclass
class Message:
    body: str


@dataclass
class MessageResponse:
    response: str

    def message(self, msg):
        self.response = msg


class TestTwilioReplyWebhook(TestCase):
    def setUp(self) -> None:
        self.factory = RequestFactory()
        self.data = {
            "MessageSid": "MSXXXX",
            "SmsSid": "SSXXXX",
            "AccountSid": "ACXXXX",
            "From": "+17742613186",
            "To": "+14092153135",
            "Body": "1",
            "NumMedia": "0",
        }

    @patch("timary.views.twilio_views.MessagingResponse")
    @patch("twilio.rest.api.v2010.account.message.MessageList.list")
    def test_no_invoices_left_to_sms(self, message_list_mock, message_response_mock):
        invoice = InvoiceFactory(user__phone_number="+17742613186")

        message_list_mock.return_value = [
            {},
            Message(f"How many hours to log hours for: {invoice.title}"),
        ]
        message_response_mock.return_value = MessageResponse(response="")

        request = self.factory.post(
            reverse("timary:twilio_reply"),
            data=self.data,
        )

        with override_settings(DEBUG=True):
            response = twilio_view(twilio_reply(request))

        self.assertEqual(response.response, "All set for today. Keep it up!")
        self.assertEqual(DailyHoursInput.objects.count(), 1)
        self.assertEqual(DailyHoursInput.objects.first().hours, 1)

    @patch("timary.views.twilio_views.MessagingResponse")
    @patch("twilio.rest.api.v2010.account.message.MessageList.list")
    def test_1_invoice_left_to_sms(self, message_list_mock, message_response_mock):
        user = UserFactory(phone_number="+17742613186")
        invoice = InvoiceFactory(user=user)
        invoice2 = InvoiceFactory(user=user)

        # FIRST INVOICE SMS SENT
        message_list_mock.return_value = [
            {},
            Message(f"How many hours to log hours for: {invoice.title}"),
        ]
        message_response_mock.return_value = MessageResponse(response="")

        request = self.factory.post(
            reverse("timary:twilio_reply"),
            data=self.data,
        )

        with override_settings(DEBUG=True):
            response = twilio_view(twilio_reply(request))

        self.assertEqual(
            response.response, f"How many hours to log hours for: {invoice2.title}"
        )
        self.assertEqual(DailyHoursInput.objects.count(), 1)

        # SECOND INVOICE SMS SENT
        message_list_mock.return_value = [
            {},
            Message(f"How many hours to log hours for: {invoice2.title}"),
        ]
        updated_data = self.data.copy()
        updated_data["Body"] = "2"
        request = self.factory.post(
            reverse("timary:twilio_reply"),
            data=updated_data,
        )

        with override_settings(DEBUG=True):
            response = twilio_view(twilio_reply(request))

        self.assertEqual(response.response, "All set for today. Keep it up!")
        self.assertEqual(DailyHoursInput.objects.count(), 2)
        self.assertEqual(
            DailyHoursInput.objects.aggregate(total=Sum("hours"))["total"], 3
        )

    @patch("timary.views.twilio_views.MessagingResponse")
    @patch("twilio.rest.api.v2010.account.message.MessageList.list")
    def test_invalid_response_type_in_body(
        self, message_list_mock, message_response_mock
    ):
        invoice = InvoiceFactory(user__phone_number="+17742613186")

        message_list_mock.return_value = [
            {},
            Message(f"How many hours to log hours for: {invoice.title}"),
        ]
        message_response_mock.return_value = MessageResponse(response="")

        invalid_data = self.data.copy()
        invalid_data["Body"] = "abc"

        request = self.factory.post(
            reverse("timary:twilio_reply"),
            data=invalid_data,
        )

        with override_settings(DEBUG=True):
            response = twilio_view(twilio_reply(request))

        self.assertEqual(
            response.response,
            f"Wrong input, only numbers please. How many hours to log hours for: {invoice.title}",
        )
        self.assertEqual(DailyHoursInput.objects.count(), 0)

    @patch("timary.views.twilio_views.MessagingResponse")
    @patch("twilio.rest.api.v2010.account.message.MessageList.list")
    def test_body_has_to_be_greater_than_half_hour(
        self, message_list_mock, message_response_mock
    ):
        invoice = InvoiceFactory(user__phone_number="+17742613186")

        # FIRST INVOICE SENT, NOT ENOUGH HOURS
        message_list_mock.return_value = [
            {},
            Message(f"How many hours to log hours for: {invoice.title}"),
        ]
        message_response_mock.return_value = MessageResponse(response="")

        invalid_data = self.data.copy()
        invalid_data["Body"] = "0"

        request = self.factory.post(
            reverse("timary:twilio_reply"),
            data=invalid_data,
        )

        with override_settings(DEBUG=True):
            response = twilio_view(twilio_reply(request))

        self.assertEqual(
            response.response,
            f"Hours have to be greater than 0.5. How many hours to log hours for: {invoice.title}",
        )
        self.assertEqual(DailyHoursInput.objects.count(), 0)

        # SECOND INVOICE SENT, HOURS LOGGED MORE THAN 30 MINUTES
        message_list_mock.return_value = [
            {},
            Message(
                f"Hours have to be greater than 0.5. How many hours to log hours for: {invoice.title}"
            ),
        ]
        updated_data = self.data.copy()
        updated_data["Body"] = "0.6"
        request = self.factory.post(
            reverse("timary:twilio_reply"),
            data=updated_data,
        )

        with override_settings(DEBUG=True):
            response = twilio_view(twilio_reply(request))

        self.assertEqual(response.response, "All set for today. Keep it up!")
        self.assertEqual(DailyHoursInput.objects.count(), 1)
