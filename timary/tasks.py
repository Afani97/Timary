import datetime
from datetime import date, timedelta
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from django.db.models import Q, Sum
from django_q.tasks import async_task, schedule

from timary.invoice_builder import InvoiceBuilder
from timary.models import (
    HoursLineItem,
    Invoice,
    SentInvoice,
    User,
    IntervalInvoice,
    WeeklyInvoice,
    MilestoneInvoice,
)
from timary.services.email_service import EmailService
from timary.services.twilio_service import TwilioClient


def gather_recurring_hours():
    all_recurring_hours = HoursLineItem.objects.exclude(
        Q(recurring_logic__exact={}) | Q(recurring_logic__isnull=True)
    ).exclude(invoice__is_archived=True)

    is_today_saturday = date.today().weekday() == 5

    new_hours_added = []

    for recurring_hour in all_recurring_hours:
        if recurring_hour.is_recurring_date_today():

            new_hours = HoursLineItem.objects.create(
                quantity=recurring_hour.quantity,
                date_tracked=date.today(),
                invoice=recurring_hour.invoice,
                recurring_logic=recurring_hour.recurring_logic,
            )
            new_hours_added.append(new_hours)

            # Prevent double stacking of hours, instead just update new hours to have the recurring logic
            recurring_hour.cancel_recurring_hour()

            if is_today_saturday:
                new_hours.update_recurring_starting_weeks()

        if is_today_saturday and recurring_hour.recurring_logic:
            recurring_hour.update_recurring_starting_weeks()

    return f"{len(new_hours_added)} hours added."


def gather_invoices():
    today = date.today()
    tomorrow = today + timedelta(days=1)
    paused_query = Q(is_paused=False)
    archived_query = Q(is_archived=False)
    today_query = Q(
        next_date__day=today.day,
        next_date__month=today.month,
        next_date__year=today.year,
    )
    invoices_sent_today = IntervalInvoice.objects.filter(
        paused_query & today_query & archived_query
    )
    for invoice in invoices_sent_today:
        _ = async_task(send_invoice, invoice.id)

    tomorrow_query = Q(
        next_date__day=tomorrow.day,
        next_date__month=tomorrow.month,
        next_date__year=tomorrow.year,
    )
    invoices_sent_tomorrow = IntervalInvoice.objects.filter(
        paused_query & tomorrow_query & archived_query
    )
    for invoice in invoices_sent_tomorrow:
        _ = async_task(send_invoice_preview, invoice.id)

    invoices_sent = len(list(invoices_sent_today) + list(invoices_sent_tomorrow))

    if today.weekday() == 0:
        invoices_sent_only_on_mondays = WeeklyInvoice.objects.filter(
            paused_query & archived_query
        )

        for invoice in invoices_sent_only_on_mondays:
            _ = async_task(send_invoice, invoice.id)
        invoices_sent += len(list(invoices_sent_only_on_mondays))

    EmailService.send_plain(
        f"Sent out {invoices_sent} invoices",
        f'{date.strftime(today, "%m/%-d/%Y")}, there were {invoices_sent} invoices sent out.',
        "aristotelf@gmail.com",
    )

    return f"Invoices sent: {invoices_sent}"


def send_invoice(invoice_id):
    invoice = Invoice.objects.get(id=invoice_id)
    if not invoice.user.settings["subscription_active"]:
        return
    hours_tracked, total_amount = invoice.get_hours_stats()
    if invoice.invoice_type() == "interval" and hours_tracked.count() <= 0:
        # There is nothing to invoice, update next date for invoice email.
        invoice.update()
        return
    today = date.today()
    current_month = date.strftime(today, "%m/%Y")

    msg_subject = f"{invoice.title }'s Invoice from { invoice.user.first_name } for { current_month }"

    sent_invoice = SentInvoice.create(invoice=invoice)
    for hour in hours_tracked:
        hour.sent_invoice_id = sent_invoice.id
        hour.save(update_fields=["sent_invoice_id"])

    msg_body = InvoiceBuilder(sent_invoice.user).send_invoice(
        {
            "sent_invoice": sent_invoice,
            "line_items": sent_invoice.get_hours_tracked(),
        }
    )
    EmailService.send_html(
        msg_subject,
        msg_body,
        invoice.client_email,
    )
    invoice.update()


def send_invoice_preview(invoice_id):
    invoice = Invoice.objects.get(id=invoice_id)
    if not invoice.user.settings["subscription_active"]:
        return
    hours_tracked, total_amount = invoice.get_hours_stats()
    msg_body = InvoiceBuilder(invoice.user).send_invoice_preview(
        {
            "invoice": invoice,
            "hours_tracked": hours_tracked,
            "total_amount": total_amount,
        }
    )
    EmailService.send_html(
        "Pssst! Here is a sneak peek of the invoice going out tomorrow. Make any modifications before it's sent "
        "tomorrow morning",
        msg_body,
        invoice.user.email,
    )


def send_reminder_sms():
    users = User.objects.exclude(
        Q(phone_number__isnull=True) | Q(phone_number__exact="")
    ).prefetch_related("invoices")

    invoices_sent_count = 0
    weekday = date.today().strftime("%a")
    for user in users:
        if weekday not in user.settings.get("phone_number_availability"):
            continue
        if not user.settings["subscription_active"]:
            continue
        remaining_invoices = user.invoices_not_logged()
        if remaining_invoices:
            invoice = remaining_invoices.pop()
            TwilioClient.log_hours(invoice)
            invoices_sent_count += 1
            if user.phone_number_repeat_sms:
                _ = schedule(
                    "timary.tasks.remind_sms_again",
                    user.email,
                    schedule_type="O",
                    next_run=datetime.datetime.today() + timedelta(hours=1),
                )
    return f"{invoices_sent_count} message(s) sent."


def remind_sms_again(user_email):
    user = User.objects.get(email=user_email)
    remaining_invoices = user.invoices_not_logged()
    invoices_sent_count = 0
    if remaining_invoices:
        invoice = remaining_invoices.pop()
        TwilioClient.log_hours(invoice)
        invoices_sent_count += 1
    return f"{invoices_sent_count} message(s) resent."


def send_weekly_updates():
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    all_recurring_invoices = IntervalInvoice.objects.exclude(is_archived=True).union(
        MilestoneInvoice.objects.exclude(is_archived=True)
    )
    for invoice in all_recurring_invoices:
        if not invoice.user.settings["subscription_active"]:
            continue
        hours = invoice.get_hours_tracked()
        if not hours:
            continue
        hours_tracked_this_week = hours.filter(
            date_tracked__range=(week_start, today)
        ).annotate(cost=invoice.invoice_rate * Sum("quantity"))
        if not hours:
            continue

        total_hours = hours_tracked_this_week.aggregate(total_hours=Sum("quantity"))
        total_cost_amount = 0
        if total_hours["total_hours"]:
            total_cost_amount = total_hours["total_hours"] * invoice.invoice_rate
        msg_body = InvoiceBuilder(invoice.user).send_invoice_preview(
            {
                "invoice": invoice,
                "hours_tracked": hours_tracked_this_week,
                "total_amount": total_cost_amount,
            }
        )
        EmailService.send_html(
            f"Here is a weekly progress update for {invoice.title}",
            msg_body,
            invoice.client_email,
        )


def backup_db_file():
    base_dir = Path(__file__).resolve().parent.parent
    file = base_dir / "db.sqlite3"
    # Upload the file
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )
    try:
        _ = s3_client.upload_file(
            file.name, settings.AWS_STORAGE_BUCKET_NAME, "db_backups/backup.sqlite3"
        )
    except ClientError:
        return False
    return True
