import datetime
from dataclasses import dataclass
from unittest.mock import patch

from django.db.models import Sum
from django.test import TestCase
from django.test.client import RequestFactory
from django.test.utils import override_settings
from django.urls import reverse
from django_twilio.decorators import twilio_view

from timary.models import DailyHoursInput, User
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

    @patch("timary.tasks.date")
    def test_cannot_send_reminder_as_starter(self, today_mock):
        today_mock.today.return_value = datetime.date(2022, 1, 10)
        today_mock.side_effect = lambda *args, **kw: datetime.date(*args, **kw)

        UserFactory(
            phone_number_availability=["Mon"],
            membership_tier=User.MembershipTier.STARTER,
        )

        invoices_sent = send_reminder_sms()
        self.assertEqual("0 message(s) sent.", invoices_sent)

    @patch("twilio.rest.api.v2010.account.message.MessageList.create")
    @patch("timary.tasks.date")
    def test_can_send_reminder_as_professional(self, today_mock, message_create_mock):
        today_mock.today.return_value = datetime.date(2022, 1, 10)
        today_mock.side_effect = lambda *args, **kw: datetime.date(*args, **kw)
        message_create_mock.return_value = None

        InvoiceFactory(
            user__phone_number_availability=["Mon"],
            user__membership_tier=User.MembershipTier.PROFESSIONAL,
        )

        invoices_sent = send_reminder_sms()
        self.assertEqual("1 message(s) sent.", invoices_sent)

    @patch("twilio.rest.api.v2010.account.message.MessageList.create")
    @patch("timary.tasks.date")
    def test_can_send_reminder_as_business(self, today_mock, message_create_mock):
        today_mock.today.return_value = datetime.date(2022, 1, 10)
        today_mock.side_effect = lambda *args, **kw: datetime.date(*args, **kw)
        message_create_mock.return_value = None

        InvoiceFactory(
            user__phone_number_availability=["Mon"],
            user__membership_tier=User.MembershipTier.BUSINESS,
        )

        invoices_sent = send_reminder_sms()
        self.assertEqual("1 message(s) sent.", invoices_sent)


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
        self.phone_number = "+17742613186"
        self.user = UserFactory(phone_number=self.phone_number)
        self.data = {
            "MessageSid": "MSXXXX",
            "SmsSid": "SSXXXX",
            "AccountSid": "ACXXXX",
            "From": "+17742613186",
            "To": self.user.phone_number,
            "Body": "1",
            "NumMedia": "0",
        }

    @patch("timary.views.twilio_views.MessagingResponse")
    @patch("twilio.rest.api.v2010.account.message.MessageList.list")
    def test_no_invoices_left_to_sms(self, message_list_mock, message_response_mock):
        invoice = InvoiceFactory(user=self.user)

        message_list_mock.return_value = [
            Message(f"How many hours to log for: {invoice.title}.")
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
        invoice = InvoiceFactory(user=self.user)
        invoice2 = InvoiceFactory(user=self.user)

        # FIRST INVOICE SMS SENT
        message_list_mock.return_value = [
            Message(f"How many hours to log for: {invoice.title}.")
        ]
        message_response_mock.return_value = MessageResponse(response="")

        request = self.factory.post(
            reverse("timary:twilio_reply"),
            data=self.data,
        )

        with override_settings(DEBUG=True):
            response = twilio_view(twilio_reply(request))

        self.assertIn(f"How many hours to log for: {invoice2.title}", response.response)
        self.assertEqual(DailyHoursInput.objects.count(), 1)

        # SECOND INVOICE SMS SENT
        message_list_mock.return_value = [
            Message(f"How many hours to log for: {invoice2.title}.")
        ]
        self.data["Body"] = "2"
        request = self.factory.post(
            reverse("timary:twilio_reply"),
            data=self.data,
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
        invoice = InvoiceFactory(user=self.user)

        message_list_mock.return_value = [
            Message(f"How many hours to log for: {invoice.title}.")
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
            f"Wrong input, only numbers please. How many hours to log for: {invoice.title}. Reply 'S' to skip",
        )
        self.assertEqual(DailyHoursInput.objects.count(), 0)

    @patch("timary.services.twilio_service.TwilioClient.send_message")
    @patch("timary.services.twilio_service.TwilioClient.log_hours")
    @patch("timary.views.twilio_views.MessagingResponse")
    @patch("twilio.rest.api.v2010.account.message.MessageList.list")
    def test_twilio_get_messages_error_resends_message_to_log(
        self,
        message_list_mock,
        message_response_mock,
        log_hours_mock,
        send_message_mock,
    ):
        log_hours_mock.return_value = None
        send_message_mock.return_value = None
        invoice = InvoiceFactory(user=self.user)

        message_list_mock.return_value = [None]
        message_response_mock.return_value = MessageResponse(response="")

        # FIRST INVOICE SENT, ERROR ON TWILIO SIDE
        request = self.factory.post(
            reverse("timary:twilio_reply"),
            data=self.data,
        )

        with override_settings(DEBUG=True):
            response = twilio_view(twilio_reply(request))

        # WAS NOT ABLE TO GET RECENT MESSAGES, THEREFORE NOTHING TO LOG FOR
        # RESEND LATEST MESSAGE
        self.assertEqual(DailyHoursInput.objects.count(), 0)

        # RESEND INVOICE SMS
        message_list_mock.return_value = [
            Message(f"How many hours to log for: {invoice.title}.")
        ]
        message_response_mock.return_value = MessageResponse(response="")

        request = self.factory.post(
            reverse("timary:twilio_reply"),
            data=self.data,
        )

        with override_settings(DEBUG=True):
            response = twilio_view(twilio_reply(request))

        self.assertIn("All set for today. Keep it up!", response.response)
        self.assertEqual(DailyHoursInput.objects.count(), 1)

    @patch("timary.views.twilio_views.MessagingResponse")
    @patch("twilio.rest.api.v2010.account.message.MessageList.list")
    def test_body_has_to_be_greater_than_half_hour(
        self, message_list_mock, message_response_mock
    ):
        invoice = InvoiceFactory(user=self.user)

        # FIRST INVOICE SENT, NOT ENOUGH HOURS
        message_list_mock.return_value = [
            Message(f"How many hours to log for: {invoice.title}.")
        ]
        message_response_mock.return_value = MessageResponse(response="")

        invalid_data = self.data.copy()
        invalid_data["Body"] = "-1"

        request = self.factory.post(
            reverse("timary:twilio_reply"),
            data=invalid_data,
        )

        with override_settings(DEBUG=True):
            response = twilio_view(twilio_reply(request))

        self.assertEqual(
            response.response,
            f"Hours have to be between 0 and 24. How many hours to log for: {invoice.title}. Reply 'S' to skip",
        )
        self.assertEqual(DailyHoursInput.objects.count(), 0)

        # SECOND INVOICE SENT, HOURS LOGGED MORE THAN 30 MINUTES
        message_list_mock.return_value = [
            Message(
                f"Hours have to be greater than 0. How many hours to log for: {invoice.title}. Reply 'S' to skip"
            )
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

    @patch("timary.views.twilio_views.MessagingResponse")
    @patch("twilio.rest.api.v2010.account.message.MessageList.list")
    def test_body_has_to_be_less_than_24(
        self, message_list_mock, message_response_mock
    ):
        invoice = InvoiceFactory(user=self.user)

        # FIRST INVOICE SENT, NOT ENOUGH HOURS
        message_list_mock.return_value = [
            Message(f"How many hours to log for: {invoice.title}.")
        ]
        message_response_mock.return_value = MessageResponse(response="")

        invalid_data = self.data.copy()
        invalid_data["Body"] = "25"

        request = self.factory.post(
            reverse("timary:twilio_reply"),
            data=invalid_data,
        )

        with override_settings(DEBUG=True):
            response = twilio_view(twilio_reply(request))

        self.assertEqual(
            response.response,
            f"Hours have to be between 0 and 24. How many hours to log for: {invoice.title}. Reply 'S' to skip",
        )
        self.assertEqual(DailyHoursInput.objects.count(), 0)

        # SECOND INVOICE SENT, HOURS LOGGED MORE THAN 30 MINUTES
        message_list_mock.return_value = [
            Message(
                f"Hours have to be greater than 0. How many hours to log for: {invoice.title}. Reply 'S' to skip"
            )
        ]
        updated_data = self.data.copy()
        updated_data["Body"] = "5"
        request = self.factory.post(
            reverse("timary:twilio_reply"),
            data=updated_data,
        )

        with override_settings(DEBUG=True):
            response = twilio_view(twilio_reply(request))

        self.assertEqual(response.response, "All set for today. Keep it up!")
        self.assertEqual(DailyHoursInput.objects.count(), 1)

    @patch("timary.views.twilio_views.MessagingResponse")
    @patch("twilio.rest.api.v2010.account.message.MessageList.list")
    def test_skip_invoice(self, message_list_mock, message_response_mock):
        """Since we hide hours logged with '0' hours, this is a hack to 'skip'"""
        invoice = InvoiceFactory(title="Invoice1", user=self.user)
        invoice2 = InvoiceFactory(title="Invoice2", user=self.user)
        self.data["Body"] = "S"

        # FIRST INVOICE SMS SENT
        message_list_mock.return_value = [
            Message(f"How many hours to log for: {invoice.title}. Reply 'S' to skip")
        ]
        message_response_mock.return_value = MessageResponse(response="")

        request = self.factory.post(
            reverse("timary:twilio_reply"),
            data=self.data,
        )

        with override_settings(DEBUG=True):
            response = twilio_view(twilio_reply(request))

        self.assertIn(
            f"How many hours to log for: {invoice2.title}.", response.response
        )
        self.assertEqual(invoice.get_hours_tracked().count(), 0)

        # SECOND INVOICE SMS SENT
        message_list_mock.return_value = [
            Message(f"How many hours to log for: {invoice2.title}.")
        ]

        self.data["Body"] = "2"
        request = self.factory.post(
            reverse("timary:twilio_reply"),
            data=self.data,
        )

        with override_settings(DEBUG=True):
            response = twilio_view(twilio_reply(request))

        self.assertEqual(response.response, "All set for today. Keep it up!")
        self.assertEqual(invoice2.get_hours_tracked().count(), 1)
        self.assertEqual(
            DailyHoursInput.objects.aggregate(total=Sum("hours"))["total"], 2
        )
