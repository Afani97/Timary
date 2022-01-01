from datetime import date, timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils.timezone import localtime, now
from django_q.tasks import async_task
from twilio.rest import Client

from timary.models import Invoice, SentInvoice, User


def gather_invoices():
    today = localtime(now()).date()
    null_query = Q(next_date__isnull=False)
    today_query = Q(
        next_date__day=today.day,
        next_date__month=today.month,
        next_date__year=today.year,
    )
    invoices = Invoice.objects.filter(null_query & today_query)
    for invoice in invoices:
        _ = async_task(send_invoice, invoice.id)

    send_mail(
        f"Sent out {len(invoices)} invoices",
        f'{date.strftime(today, "%m/%-d/%Y")}, there were {len(invoices)} invoices sent out.',
        None,
        recipient_list=["aristotelf@gmail.com"],
        fail_silently=True,
    )

    return f"Invoices sent: {invoices.count()}"


def send_invoice(invoice_id):
    invoice = Invoice.objects.get(id=invoice_id)
    hours_tracked, total_amount = invoice.get_hours_stats()
    if hours_tracked.count() <= 0:
        # There is nothing to invoice, update next date for invoice email.
        invoice.calculate_next_date()
        return
    today = localtime(now()).date()
    current_month = date.strftime(today, "%m/%Y")

    msg_subject = render_to_string(
        "email/invoice_subject.html",
        {"invoice": invoice, "current_month": current_month},
    ).strip()

    sent_invoice = SentInvoice.objects.create(
        hours_start_date=hours_tracked.first().date_tracked or None,
        hours_end_date=hours_tracked.last().date_tracked or None,
        date_sent=today,
        invoice=invoice,
        user=invoice.user,
        total_price=total_amount,
    )
    msg_body = render_to_string(
        "email/styled_email.html",
        {
            "site_url": settings.SITE_URL,
            "user_name": invoice.user.first_name,
            "next_weeks_date": today + timedelta(weeks=1),
            "recipient_name": invoice.email_recipient_name,
            "total_amount": total_amount,
            "invoice_id": sent_invoice.id,
            "invoice": invoice,
            "hours_tracked": hours_tracked,
            "todays_date": today,
        },
    )
    send_mail(
        msg_subject,
        None,
        None,
        recipient_list=[invoice.email_recipient],
        fail_silently=False,
        html_message=msg_body,
    )
    invoice.calculate_next_date()


def send_reminder_sms():
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    users = User.objects.exclude(
        Q(phone_number__isnull=True) | Q(phone_number__exact="")
    ).prefetch_related("invoices")
    invoices_sent_count = 0
    for user in users:
        remaining_invoices = user.invoices_not_logged
        if len(remaining_invoices) > 0:
            invoice = remaining_invoices.pop()
            _ = client.messages.create(
                to=user.formatted_phone_number,
                from_=settings.TWILIO_PHONE_NUMBER,
                body=f"How many hours to log for: {invoice.title}",
            )
            invoices_sent_count += 1
    return f"{invoices_sent_count} message(s) sent."
