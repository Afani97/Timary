from datetime import date, timedelta
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from django.db.models import Q, Sum
from django.utils import timezone
from django_q.tasks import async_task, schedule

from timary.invoice_builder import InvoiceBuilder
from timary.models import (
    HoursLineItem,
    IntervalInvoice,
    Invoice,
    MilestoneInvoice,
    SentInvoice,
    SingleInvoice,
    User,
    WeeklyInvoice,
)
from timary.services.email_service import EmailService
from timary.services.twilio_service import TwilioClient


def gather_recurring_hours():
    all_recurring_hours = HoursLineItem.objects.exclude(
        Q(recurring_logic__exact={}) | Q(recurring_logic__isnull=True)
    ).exclude(invoice__is_archived=True)

    today = timezone.now()
    is_today_saturday = today.weekday() == 5

    new_hours_added = []

    for recurring_hour in all_recurring_hours:
        if recurring_hour.is_recurring_date_today():

            new_hours = HoursLineItem.objects.create(
                quantity=recurring_hour.quantity,
                date_tracked=today,
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
    today = timezone.now()
    tomorrow = today + timedelta(days=1)
    paused_query = Q(is_paused=False)
    archived_query = Q(is_archived=False)
    user_active_query = Q(
        user__stripe_subscription_status=User.StripeSubscriptionStatus.INACTIVE
    )
    today_range_query = (
        today.replace(hour=0, minute=0, second=0),
        today.replace(hour=23, minute=59, second=59),
    )
    invoices_sent_today = (
        IntervalInvoice.objects.filter(paused_query & archived_query)
        .filter(next_date__range=today_range_query)
        .exclude(user_active_query)
    )
    for invoice in invoices_sent_today:
        _ = async_task(send_invoice, invoice.id)

    tomorrow_range_query = (
        tomorrow.replace(hour=0, minute=0, second=0),
        tomorrow.replace(hour=23, minute=59, second=59),
    )
    invoices_sent_tomorrow = (
        IntervalInvoice.objects.filter(paused_query & archived_query)
        .filter(next_date__range=tomorrow_range_query)
        .exclude(user_active_query)
    )
    for invoice in invoices_sent_tomorrow:
        _ = async_task(send_invoice_preview, invoice.id)

    invoices_sent = len(list(invoices_sent_today) + list(invoices_sent_tomorrow))

    if today.weekday() == 0:
        invoices_sent_only_on_mondays = WeeklyInvoice.objects.filter(
            paused_query & archived_query
        ).exclude(user_active_query)

        for invoice in invoices_sent_only_on_mondays:
            _ = async_task(send_invoice, invoice.id)
        invoices_sent += len(list(invoices_sent_only_on_mondays))

    return f"Invoices sent: {invoices_sent}"


def gather_single_invoices_before_due_date():
    today = timezone.now()
    one_day_before = today + timedelta(days=1)
    two_days_before = today + timedelta(days=2)
    archived_query = Q(is_archived=False)
    user_active_query = Q(
        user__stripe_subscription_status=User.StripeSubscriptionStatus.INACTIVE
    )
    due_in_one_day = Q(
        due_date__day=one_day_before.day,
        due_date__month=one_day_before.month,
        due_date__year=one_day_before.year,
    )
    due_in_two_days = Q(
        due_date__day=two_days_before.day,
        due_date__month=two_days_before.month,
        due_date__year=two_days_before.year,
    )
    invoices_due_in_one_day = SingleInvoice.objects.filter(
        due_in_one_day & archived_query
    ).exclude(user_active_query)
    for invoice in invoices_due_in_one_day:
        _ = async_task(send_invoice_reminder, invoice.id)

    invoices_due_in_two_days = SingleInvoice.objects.filter(
        due_in_two_days & archived_query
    ).exclude(user_active_query)
    for invoice in invoices_due_in_two_days:
        _ = async_task(send_invoice_reminder, invoice.id)

    invoices_sent = len(list(invoices_due_in_one_day) + list(invoices_due_in_two_days))

    return f"Invoices sent: {invoices_sent}"


def send_invoice_reminder(invoice_id):
    single_invoice_obj = SingleInvoice.objects.get(id=invoice_id)
    sent_invoice = single_invoice_obj.get_sent_invoice()
    if sent_invoice and (
        sent_invoice.paid_status == SentInvoice.PaidStatus.PENDING
        or sent_invoice.paid_status == SentInvoice.PaidStatus.PAID
    ):
        return

    today = timezone.now()
    current_month = date.strftime(today, "%m/%Y")

    line_items = single_invoice_obj.line_items.all()
    if sent_invoice is None:
        sent_invoice = SentInvoice.objects.create(
            date_sent=today,
            invoice=single_invoice_obj,
            user=single_invoice_obj.user,
            total_price=single_invoice_obj.balance_due,
        )
    else:
        sent_invoice.date_sent = today
        sent_invoice.total_price = single_invoice_obj.balance_due
        sent_invoice.save()

    for line_item in line_items:
        line_item.sent_invoice_id = sent_invoice.id
        line_item.save()

    msg_body = InvoiceBuilder(sent_invoice.user).send_invoice(
        {
            "sent_invoice": sent_invoice,
            "line_items": sent_invoice.get_rendered_line_items(),
        }
    )

    EmailService.send_html(
        f"{single_invoice_obj.title}'s Invoice from {single_invoice_obj.user.first_name} for {current_month}",
        msg_body,
        [single_invoice_obj.client_email, single_invoice_obj.client_second_email],
    )


def send_invoice(invoice_id):
    invoice = Invoice.objects.get(id=invoice_id)
    if not invoice.user.settings["subscription_active"]:
        return
    hours_tracked, total_amount = invoice.get_hours_stats()
    if invoice.invoice_type() == "interval" and hours_tracked.count() <= 0:
        # There is nothing to invoice, update next date for invoice email.
        invoice.update()
        return
    today = timezone.now()
    current_month = date.strftime(today, "%m/%Y")

    msg_subject = f"{invoice.title }'s Invoice from { invoice.user.first_name } for { current_month }"

    sent_invoice = SentInvoice.create(invoice=invoice)
    for hour in hours_tracked:
        hour.sent_invoice_id = sent_invoice.id
        hour.save(update_fields=["sent_invoice_id"])

    msg_body = InvoiceBuilder(sent_invoice.user).send_invoice(
        {
            "sent_invoice": sent_invoice,
            "line_items": sent_invoice.get_rendered_line_items(),
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
    weekday = timezone.now().strftime("%a")
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
                    next_run=timezone.now() + timedelta(hours=1),
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
    today = timezone.now()
    week_start = today - timedelta(days=today.weekday())
    all_recurring_invoices = Invoice.objects.instance_of(
        IntervalInvoice
    ) | Invoice.objects.instance_of(MilestoneInvoice)

    for invoice in all_recurring_invoices:
        if not invoice.user.settings["subscription_active"]:
            continue
        hours = invoice.get_hours_tracked()
        if not hours:
            continue
        hours_tracked_this_week = hours.filter(
            date_tracked__range=(week_start, today)
        ).annotate(cost=invoice.rate * Sum("quantity"))
        if not hours:
            continue

        total_hours = hours_tracked_this_week.aggregate(total_hours=Sum("quantity"))
        total_cost_amount = 0
        if total_hours["total_hours"]:
            total_cost_amount = total_hours["total_hours"] * invoice.rate
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
