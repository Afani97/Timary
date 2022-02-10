import datetime

from django.conf import settings
from twilio.rest import Client


class TwilioClient:
    @staticmethod
    def client():
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        return client

    @staticmethod
    def sent_payment_success(sent_invoice):
        if sent_invoice.invoice.user.phone_number:
            _ = TwilioClient.client().messages.create(
                to=sent_invoice.invoice.user.formatted_phone_number,
                from_=settings.TWILIO_PHONE_NUMBER,
                body=f"Invoice for {sent_invoice.invoice.title} has been paid! "
                f"You should see {sent_invoice.total_price} deposited into your bank account shortly",
            )

    @staticmethod
    def log_hours(invoice):
        _ = TwilioClient.client().messages.create(
            to=invoice.user.formatted_phone_number,
            from_=settings.TWILIO_PHONE_NUMBER,
            body=f"How many hours to log for: {invoice.title}",
        )

    @staticmethod
    def get_user_messages():
        return TwilioClient.client().messages.list(limit=2, date_sent=datetime)
