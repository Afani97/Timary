import datetime
from decimal import Decimal, InvalidOperation

from django_twilio.decorators import twilio_view
from django_twilio.request import decompose
from twilio.twiml.messaging_response import MessagingResponse

from timary.models import DailyHoursInput, User
from timary.services.twilio_service import TwilioClient


@twilio_view
def twilio_reply(request):
    twilio_request = decompose(request)
    user = User.objects.get(phone_number=twilio_request.from_)

    last_message = TwilioClient.get_user_messages()
    if not last_message or ":" not in last_message.body:
        remaining_invoices = user.invoices_not_logged
        TwilioClient.log_hours(remaining_invoices.pop())
        return

    _, invoice_title = last_message.body.split(":")
    invoice_title = invoice_title.split(".")[0]
    invoice = user.get_invoices.filter(title=invoice_title.strip()).first()

    skip = False
    if twilio_request.body.lower() == "s":
        skip = True

    if not skip:
        try:
            hours = Decimal(twilio_request.body)
        except InvalidOperation:
            r = MessagingResponse()
            r.message(
                f"Wrong input, only numbers please. How many hours to log for: {invoice.title}. Reply 'S' to skip"
            )
            return r

        if 0 < hours <= 24:
            DailyHoursInput.objects.create(
                hours=hours,
                date_tracked=datetime.date.today(),
                invoice=invoice,
            )
        else:
            r = MessagingResponse()
            r.message(
                f"Hours have to be between 0 and 24. How many hours to log for: {invoice.title}. Reply 'S' to skip"
            )
            return r
    else:
        DailyHoursInput.objects.create(
            hours=0,
            date_tracked=datetime.date.today(),
            invoice=invoice,
        )

    remaining_invoices = user.invoices_not_logged
    if remaining_invoices:
        invoice = remaining_invoices.pop()
        r = MessagingResponse()
        r.message(f"How many hours to log for: {invoice.title}. Reply 'S' to skip")
        return r
    else:
        r = MessagingResponse()
        r.message("All set for today. Keep it up!")
        return r
