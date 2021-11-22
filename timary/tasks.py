from datetime import date, timedelta

from django.core.mail import send_mail
from django.db.models import F, Q, Sum
from django.template.loader import render_to_string
from django.utils.timezone import localtime, now
from django_q.tasks import async_task

from timary.models import Invoice


def send_invoice(invoice_id):
    invoice = Invoice.objects.get(id=invoice_id)
    hours_tracked = invoice.hours_tracked.filter(
        date_tracked__gt=F("invoice__last_date")
    ).annotate(cost=F("invoice__hourly_rate") * Sum("hours"))
    total_hours_worked = hours_tracked.aggregate(total_hours=Sum("hours"))[
        "total_hours"
    ]
    if hours_tracked.count() <= 0:
        # There is nothing to invoice, update next date for invoice email.
        invoice.calculate_next_date()
        return
    todays_date = localtime(now()).date()
    current_month = date.strftime(todays_date, "%m/%Y")

    msg_subject = render_to_string(
        "email/invoice_subject.html",
        {"invoice": invoice, "current_month": current_month},
    ).strip()

    msg_body = render_to_string(
        "email/styled_email.html",
        {
            "user_name": invoice.user.user.first_name,
            "next_weeks_date": todays_date + timedelta(weeks=1),
            "recipient_name": invoice.email_recipient_name,
            "total_amount": total_hours_worked * invoice.hourly_rate,
            "invoice_id": invoice.email_id,
            "invoice": invoice,
            "hours_tracked": hours_tracked,
            "todays_date": todays_date,
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


def gather_invoices():
    todays_date = localtime(now()).date()
    null_query = Q(next_date__isnull=True)
    today_query = Q(
        next_date__day=todays_date.day,
        next_date__month=todays_date.month,
        next_date__year=todays_date.year,
    )
    invoices = Invoice.objects.filter(null_query | today_query)
    for invoice in invoices:
        _ = async_task(send_invoice, invoice.id)

    return f"Invoices sent: {invoices.count()}"
