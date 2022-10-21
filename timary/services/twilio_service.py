import datetime

from django.conf import settings
from django_twilio.client import twilio_client


class TwilioClient:
    @staticmethod
    def sent_payment_success(sent_invoice):
        if sent_invoice.invoice.user.phone_number:
            _ = twilio_client.messages.create(
                to=sent_invoice.invoice.user.formatted_phone_number,
                from_=settings.TWILIO_PHONE_NUMBER,
                body=f"Invoice for {sent_invoice.invoice.title} has been paid! "
                f"It will arrive into your bank account shortly",
            )

    @staticmethod
    def log_hours(invoice):
        _ = twilio_client.messages.create(
            to=invoice.user.formatted_phone_number,
            from_=settings.TWILIO_PHONE_NUMBER,
            body=f"How many hours to log for: {invoice.title}. Reply 'S' to skip",
        )

    @staticmethod
    def send_message(user, message):
        _ = twilio_client.messages.create(
            to=user.formatted_phone_number,
            from_=settings.TWILIO_PHONE_NUMBER,
            body=message,
        )

    @staticmethod
    def get_user_messages(user_number):
        recent_messages = twilio_client.messages.list(
            to=user_number, limit=1, date_sent=datetime
        )
        if recent_messages and len(recent_messages) == 1:
            recent_message = recent_messages[0]
            if hasattr(recent_message, "body"):
                if ":" in recent_message.body:
                    return recent_message
        return None
