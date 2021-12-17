from dataclasses import dataclass
from unittest.mock import patch

from django.test import TestCase
from django.test.client import RequestFactory
from django.test.utils import override_settings
from django.urls import reverse
from django_twilio.decorators import twilio_view

from timary.tasks import send_reminder_sms
from timary.tests.factories import InvoiceFactory
from timary.views.twilio_views import twilio_reply


class TestTwilioSendReminderSMS(TestCase):
    @patch("twilio.rest.api.v2010.account.message.MessageList.create")
    def test_send_0_messages(self, message_create_mock):
        message_create_mock.return_value = None
        invoices_sent = send_reminder_sms()
        self.assertEqual("0 message(s) sent.", invoices_sent)

    @patch("twilio.rest.api.v2010.account.message.MessageList.create")
    def test_send_1_message(self, message_create_mock):
        message_create_mock.return_value = None

        InvoiceFactory()

        invoices_sent = send_reminder_sms()
        self.assertEqual("1 message(s) sent.", invoices_sent)

    @patch("twilio.rest.api.v2010.account.message.MessageList.create")
    def test_send_3_messages(self, message_create_mock):
        message_create_mock.return_value = None

        InvoiceFactory()
        InvoiceFactory()
        InvoiceFactory()

        invoices_sent = send_reminder_sms()
        self.assertEqual("3 message(s) sent.", invoices_sent)


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
