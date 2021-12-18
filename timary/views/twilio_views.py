import datetime

from django.conf import settings
from django_twilio.decorators import twilio_view
from django_twilio.request import decompose
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse

from timary.models import DailyHoursInput, Invoice, User


@twilio_view
def twilio_reply(request):
    twilio_request = decompose(request)
    user = User.objects.get(phone_number=twilio_request.from_)

    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    messages = client.messages.list(limit=2, date_sent=datetime)

    _, invoice_title = messages[1].body.split(":")
    invoice = Invoice.objects.get(title=invoice_title.strip(), user=user)

    try:
        hours = int(twilio_request.body)
    except ValueError:
        r = MessagingResponse()
        r.message(
            f"Wrong input, only numbers please. How many hours to log hours for: {invoice.title}"
        )
        return r

    DailyHoursInput.objects.create(
        hours=hours,
        date_tracked=datetime.date.today(),
        invoice=invoice,
    )

    remaining_invoices = user.invoices_not_logged
    if len(remaining_invoices) > 0:
        invoice = remaining_invoices.pop()
        r = MessagingResponse()
        r.message(f"How many hours to log hours for: {invoice.title}")
        return r
    else:
        r = MessagingResponse()
        r.message("All set for today. Keep it up!")
        return r
