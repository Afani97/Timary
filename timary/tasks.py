from datetime import date, timedelta
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils.timezone import localtime, now
from django_q.tasks import async_task

from timary.models import Invoice, SentInvoice, User
from timary.services.email_service import EmailService
from timary.services.freshbook_service import FreshbookService
from timary.services.quickbook_service import QuickbookService
from timary.services.sage_service import SageService
from timary.services.twilio_service import TwilioClient
from timary.services.xero_service import XeroService
from timary.services.zoho_service import ZohoService


def gather_invoices():
    today = localtime(now()).date()
    tomorrow = today + timedelta(days=1)
    null_query = Q(next_date__isnull=False)
    today_query = Q(
        next_date__day=today.day,
        next_date__month=today.month,
        next_date__year=today.year,
    )
    invoices_sent_today = Invoice.objects.filter(
        null_query & today_query & Q(is_archived=False)
    )
    for invoice in invoices_sent_today:
        _ = async_task(send_invoice, invoice.id)

    tomorrow_query = Q(
        next_date__day=tomorrow.day,
        next_date__month=tomorrow.month,
        next_date__year=tomorrow.year,
    )
    invoices_sent_tomorrow = Invoice.objects.filter(
        null_query & tomorrow_query & Q(is_archived=False)
    )
    for invoice in invoices_sent_tomorrow:
        _ = async_task(send_invoice_preview, invoice.id)

    invoices_sent = len(list(invoices_sent_today) + list(invoices_sent_tomorrow))
    EmailService.send_plain(
        f"Sent out {invoices_sent} invoices",
        f'{date.strftime(today, "%m/%-d/%Y")}, there were {invoices_sent} invoices sent out.',
        "aristotelf@gmail.com",
    )

    return f"Invoices sent: {invoices_sent}"


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
    for hour in hours_tracked:
        hour.sent_invoice_id = sent_invoice.id
        hour.save()
    msg_body = render_to_string(
        "email/styled_email.html",
        {
            "can_accept_payments": invoice.user.can_accept_payments,
            "site_url": settings.SITE_URL,
            "user_name": invoice.user.first_name,
            "next_weeks_date": today + timedelta(weeks=1),
            "recipient_name": invoice.email_recipient_name,
            "total_amount": total_amount,
            "sent_invoice_id": sent_invoice.id,
            "invoice": invoice,
            "hours_tracked": hours_tracked,
            "todays_date": today,
        },
    )
    EmailService.send_html(msg_subject, msg_body, invoice.email_recipient)
    invoice.calculate_next_date()


def send_invoice_preview(invoice_id):
    invoice = Invoice.objects.get(id=invoice_id)
    hours_tracked, total_amount = invoice.get_hours_stats()
    today = localtime(now()).date()

    msg_body = render_to_string(
        "email/sneak_peak_invoice_email.html",
        {
            "user_name": invoice.user.first_name,
            "next_weeks_date": today + timedelta(weeks=1),
            "recipient_name": invoice.email_recipient_name,
            "total_amount": total_amount,
            "invoice": invoice,
            "hours_tracked": hours_tracked,
            "tomorrows_date": today + timedelta(days=1),
            "can_view_invoice_stats": invoice.user.can_view_invoice_stats,
            "site_url": settings.SITE_URL,
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
            file.name, settings.AWS_BUCKET_NAME, "db_backups/backup.sqlite3"
        )
    except ClientError:
        return False
    return True


def refresh_accounting_integration_tokens():
    """Run this every first of the month"""
    users = User.objects.filter(
        Q(membership_tier=User.MembershipTier.BUSINESS)
        | Q(membership_tier=User.MembershipTier.INVOICE_FEE)
    )
    for user in users:
        if user.quickbooks_realm_id:
            QuickbookService.get_refreshed_tokens(user)
        if user.freshbooks_account_id:
            FreshbookService.get_refreshed_tokens(user)
        if user.zoho_organization_id:
            ZohoService.get_refreshed_tokens(user)
        if user.xero_tenant_id:
            XeroService.get_refreshed_tokens(user)
        if user.sage_account_id:
            SageService.get_refreshed_tokens(user)
