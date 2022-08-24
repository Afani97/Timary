from datetime import date, timedelta
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from django.db.models import Q, Sum
from django.template.loader import render_to_string
from django_q.tasks import async_task

from timary.custom_errors import AccountingError
from timary.models import Invoice, SentInvoice, User
from timary.services.accounting_service import AccountingService
from timary.services.email_service import EmailService
from timary.services.twilio_service import TwilioClient


def gather_invoices():
    today = date.today()
    tomorrow = today + timedelta(days=1)
    null_query = Q(next_date__isnull=False)
    today_query = Q(
        next_date__day=today.day,
        next_date__month=today.month,
        next_date__year=today.year,
    )
    invoices_sent_today = Invoice.objects.filter(
        null_query
        & today_query
        & Q(is_archived=False)
        & Q(invoice_type=Invoice.InvoiceType.INTERVAL)
    )
    for invoice in invoices_sent_today:
        _ = async_task(send_invoice, invoice.id)

    tomorrow_query = Q(
        next_date__day=tomorrow.day,
        next_date__month=tomorrow.month,
        next_date__year=tomorrow.year,
    )
    invoices_sent_tomorrow = Invoice.objects.filter(
        null_query
        & tomorrow_query
        & Q(is_archived=False)
        & Q(invoice_type=Invoice.InvoiceType.INTERVAL)
    )
    for invoice in invoices_sent_tomorrow:
        _ = async_task(send_invoice_preview, invoice.id)

    invoices_sent = len(list(invoices_sent_today) + list(invoices_sent_tomorrow))

    if today.weekday() == 0:
        invoices_sent_only_on_mondays = Invoice.objects.filter(
            null_query
            & Q(is_archived=False)
            & Q(invoice_type=Invoice.InvoiceType.WEEKLY)
        )
        for invoice in invoices_sent_tomorrow:
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
    hours_tracked, total_amount = invoice.get_hours_stats()
    if (
        invoice.invoice_type != Invoice.InvoiceType.WEEKLY
        and hours_tracked.count() <= 0
    ):
        # There is nothing to invoice, update next date for invoice email.
        invoice.calculate_next_date()
        return
    today = date.today()
    current_month = date.strftime(today, "%m/%Y")

    msg_subject = f"{invoice.title }'s Invoice from { invoice.user.first_name } for { current_month }"

    sent_invoice = SentInvoice.create(invoice=invoice)
    for hour in hours_tracked:
        hour.sent_invoice_id = sent_invoice.id
        hour.save()

    msg_body = render_to_string(
        "email/sent_invoice_email.html",
        {
            "can_accept_payments": invoice.user.can_accept_payments,
            "site_url": settings.SITE_URL,
            "user_name": invoice.user.invoice_branding_properties()["user_name"],
            "next_weeks_date": invoice.user.invoice_branding_properties()[
                "next_weeks_date"
            ],
            "recipient_name": invoice.email_recipient_name,
            "total_amount": total_amount,
            "sent_invoice": sent_invoice,
            "invoice": invoice,
            "hours_tracked": hours_tracked,
            "todays_date": today,
            "invoice_branding": invoice.user.invoice_branding_properties(),
        },
    )
    EmailService.send_html(msg_subject, msg_body, invoice.email_recipient)
    invoice.calculate_next_date()
    invoice.increase_milestone_step()


def send_invoice_preview(invoice_id):
    invoice = Invoice.objects.get(id=invoice_id)
    hours_tracked, total_amount = invoice.get_hours_stats()
    today = date.today()

    msg_body = render_to_string(
        "email/sneak_peak_invoice_email.html",
        {
            "user_name": invoice.user.invoice_branding_properties().get("user_name"),
            "next_weeks_date": invoice.user.invoice_branding_properties().get(
                "next_weeks_date"
            ),
            "recipient_name": invoice.email_recipient_name,
            "total_amount": total_amount,
            "invoice": invoice,
            "hours_tracked": hours_tracked,
            "tomorrows_date": today + timedelta(days=1),
            "can_view_invoice_stats": invoice.user.can_view_invoice_stats,
            "site_url": settings.SITE_URL,
            "invoice_branding": invoice.user.invoice_branding_properties(),
        },
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
        if not user.can_receive_texts:
            continue
        if weekday not in user.settings.get("phone_number_availability"):
            continue
        remaining_invoices = user.invoices_not_logged
        if len(remaining_invoices) > 0:
            invoice = remaining_invoices.pop()
            TwilioClient.log_hours(invoice)
            invoices_sent_count += 1
    return f"{invoices_sent_count} message(s) sent."


def send_weekly_updates():
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    all_invoices = Invoice.objects.filter(is_archived=False).exclude(
        invoice_type=Invoice.InvoiceType.WEEKLY
    )
    for invoice in all_invoices:
        hours = invoice.get_hours_tracked()
        if hours:
            hours_tracked_this_week = hours.filter(
                date_tracked__range=(week_start, today)
            ).annotate(cost=invoice.invoice_rate * Sum("hours"))
            if not hours:
                continue

            total_hours = hours_tracked_this_week.aggregate(total_hours=Sum("hours"))
            total_cost_amount = 0
            if total_hours["total_hours"]:
                total_cost_amount = total_hours["total_hours"] * invoice.invoice_rate
            msg_body = render_to_string(
                "email/weekly_update_email.html",
                {
                    "site_url": settings.SITE_URL,
                    "user_name": invoice.user.invoice_branding_properties().get(
                        "user_name"
                    ),
                    "recipient_name": invoice.email_recipient_name,
                    "invoice": invoice,
                    "hours_tracked": hours_tracked_this_week,
                    "week_starting_date": week_start,
                    "todays_date": today,
                    "total_amount": total_cost_amount,
                    "invoice_branding": invoice.user.invoice_branding_properties(),
                },
            )
            EmailService.send_html(
                f"Here is a weekly progress update for {invoice.title}",
                msg_body,
                invoice.email_recipient,
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


def refresh_accounting_integration_tokens():
    """Run this every first of the month"""
    users = User.objects.filter(
        Q(membership_tier=User.MembershipTier.BUSINESS)
        | Q(membership_tier=User.MembershipTier.INVOICE_FEE)
    ).exclude(accounting_org_id__isnull=True)
    for user in users:
        try:
            AccountingService({"user": user}).refresh_tokens()
        except AccountingError as ae:
            ae.log()
