import datetime
import json
import random

from dateutil.relativedelta import relativedelta
from django.utils import timezone
from requests import Response

from timary.models import DailyHoursInput, Invoice, SentInvoice


def show_alert_message(
    response, alert_type, message, other_trigger=None, persist=False
):
    response["HX-Trigger"] = json.dumps(
        {
            other_trigger: None,
            "showMessage": {
                "alertType": f"alert-{alert_type}",
                "message": message,
                "persist": persist,
            },
        }
    )


def show_active_timer(user):
    context = {}
    if user.timer_is_active:
        active_timer_ms, timer_paused = user.timer_is_active.split(",")
        context["active_timer_ms"] = active_timer_ms
        context["timer_paused"] = timer_paused
    return context


def simulate_requests_response(status_code, error_num, message):
    failed_response = Response()
    failed_response.code = status_code
    failed_response.error_type = "expired"
    failed_response.status_code = status_code
    response_content = {"error": error_num, "message": message}
    failed_response._content = json.dumps(response_content, indent=2).encode("utf-8")
    return failed_response


def convert_hours_to_decimal_hours(time):
    convert_hours_map = [1, 1.0 / 60, 1.0 / 3600]
    try:
        dec_time = sum(
            a * b for a, b in zip(convert_hours_map, map(int, time.split(":")))
        )
    except Exception as e:
        raise e
    if not dec_time:
        raise ValueError()
    return dec_time


def generate_fake_initial_data(user):
    today = timezone.now()

    example_invoice = Invoice.objects.create(
        title="Archive Me",
        user=user,
        invoice_rate=125,
        email_recipient_name="Bob Smith",
        email_recipient="bobs@example.com",
        invoice_interval="M",
        next_date=today + datetime.timedelta(days=1),
        last_date=today,
    )
    date_times = [(today - relativedelta(months=m)).replace(day=1) for m in range(0, 6)]
    for dt in date_times:
        hours = DailyHoursInput.objects.create(
            hours=random.randint(4, 10),
            invoice=example_invoice,
            date_tracked=dt,
        )
        sent_invoice = SentInvoice.objects.create(
            invoice=example_invoice,
            user=user,
            date_sent=dt,
            total_price=hours.hours * example_invoice.invoice_rate,
            paid_status=random.randint(1, 3),
        )
        hours.sent_invoice_id = sent_invoice.id
        hours.save()

    from django_q.tasks import schedule

    schedule(
        "timary.tasks.delete_example_invoices",
        str(example_invoice.id),
        schedule_type="O",
        next_run=today + datetime.timedelta(weeks=1),
    )
