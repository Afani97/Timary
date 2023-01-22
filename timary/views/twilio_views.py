from decimal import Decimal, InvalidOperation

from django.utils import timezone
from django_twilio.decorators import twilio_view
from django_twilio.request import decompose
from twilio.twiml.messaging_response import MessagingResponse

from timary.models import HoursLineItem, User
from timary.services.twilio_service import TwilioClient
from timary.utils import convert_hours_to_decimal_hours


@twilio_view
def twilio_reply(request):
    twilio_request = decompose(request)
    user = User.objects.get(phone_number=twilio_request.from_)

    last_message = TwilioClient.get_user_messages(user.formatted_phone_number)
    if not last_message:
        remaining_invoices = user.invoices_not_logged()
        if remaining_invoices:
            TwilioClient.log_hours(remaining_invoices.pop())
        else:
            TwilioClient.send_message(user, "All set for today. Keep it up!")
        return MessagingResponse()

    _, invoice_title = last_message.body.rsplit(":", maxsplit=1)
    invoice_title = invoice_title.split(".")[0].strip()
    invoices = user.get_invoices.filter(title__exact=invoice_title)
    invoice = None
    if invoices.count() == 1:
        invoice = invoices.first()

    if not invoice:
        r = MessagingResponse()
        r.message(f"Unable to track hours for {invoice_title}.")
        return r

    skip = False
    if twilio_request.body.lower() == "s":
        skip = True

    if not skip:
        # Normal decimal hours
        try:
            hours = Decimal(twilio_request.body)
        except InvalidOperation:
            # Hours entered as 1:30 -> 1.5 hours
            if ":" in twilio_request.body:
                try:
                    hours = convert_hours_to_decimal_hours(twilio_request.body)
                except Exception:
                    r = MessagingResponse()
                    r.message(
                        f"Wrong input, allowed formats are '1.5' or '1:30'. "
                        f"How many hours to log for: {invoice.title}. Reply 'S' to skip"
                    )
                    return r
            else:
                r = MessagingResponse()
                r.message(
                    f"Wrong input, allowed formats are '1.5' or '1:30'. "
                    f"How many hours to log for: {invoice.title}. Reply 'S' to skip"
                )
                return r

        if hours and 0 < hours <= 24:
            HoursLineItem.objects.create(
                quantity=hours,
                date_tracked=timezone.now(),
                invoice=invoice,
            )
        else:
            r = MessagingResponse()
            r.message(
                f"Hours have to be between 0 and 24. How many hours to log for: {invoice.title}. Reply 'S' to skip"
            )
            return r
    else:
        HoursLineItem.objects.create(
            quantity=0,
            date_tracked=timezone.now(),
            invoice=invoice,
        )

    remaining_invoices = user.invoices_not_logged()
    if remaining_invoices:
        invoice = remaining_invoices.pop()
        r = MessagingResponse()
        r.message(f"How many hours to log for: {invoice.title}. Reply 'S' to skip")
        return r
    else:
        r = MessagingResponse()
        r.message("All set for today. Keep it up!")
        return r
