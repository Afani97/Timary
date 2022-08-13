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

    messages = TwilioClient.get_user_messages()

    _, invoice_title = messages[1].body.split(":")
    invoice_title, _ = invoice_title.split(".")
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
                f"Wrong input, only numbers please. How many hours to log for: {invoice.title}."
            )
            return r

        if hours > 0:
            DailyHoursInput.objects.create(
                hours=hours,
                date_tracked=datetime.date.today(),
                invoice=invoice,
            )
        else:
            r = MessagingResponse()
            r.message(
                f"Hours have to be greater than 0. How many hours to log for: {invoice.title}."
            )
            return r
    else:
        DailyHoursInput.objects.create(
            hours=0,
            date_tracked=datetime.date.today(),
            invoice=invoice,
        )

    remaining_invoices = user.invoices_not_logged
    if len(remaining_invoices) > 0:
        invoice = remaining_invoices.pop()
        r = MessagingResponse()
        r.message(f"How many hours to log for: {invoice.title}. Reply 'S' to skip")
        return r
    else:
        r = MessagingResponse()
        r.message("All set for today. Keep it up!")
        return r
