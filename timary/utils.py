import json
import zoneinfo
from datetime import datetime

from django.db.models import Sum
from django.utils import timezone
from requests import Response


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


def get_starting_week_from_date(date):
    if date.weekday() == 6:
        return date.date()
    return (date - timezone.timedelta(days=timezone.now().isoweekday() % 7)).date()


def get_date_parsed(date):
    return datetime.strftime(date, "%a").lower()


def get_users_localtime(user):
    return timezone.now().astimezone(tz=zoneinfo.ZoneInfo(user.timezone))


def generate_spreadsheet(sent_invoices):
    from tempfile import NamedTemporaryFile

    from django.http import HttpResponse
    from openpyxl import Workbook
    from openpyxl.worksheet.table import Table, TableStyleInfo

    wb = Workbook()
    ws = wb.active
    ws.title = "Your Timary audit activity"

    # add column headings. NB. these must be strings
    ws.append(
        [
            "Date Sent",
            "Date Paid",
            "Invoice #",
            "Invoice Title",
            "Total Hours",
            "Total Price",
            "Paid Status",
        ]
    )

    # add sent invoice data per row
    for sent_invoice in sent_invoices:
        total_hours = sent_invoice.invoice.line_items.aggregate(hours=Sum("quantity"))
        ws.append(
            [
                sent_invoice.date_sent.strftime("%Y-%m-%d"),
                sent_invoice.date_paid.strftime("%Y-%m-%d")
                if sent_invoice.date_paid
                else "",
                str(sent_invoice.invoice.id),
                sent_invoice.invoice.title,
                total_hours["hours"],
                str(sent_invoice.total_price),
                sent_invoice.get_paid_status_display(),
            ]
        )

    tab = Table(displayName="Table1", ref=f"A1:G{len(sent_invoices) + 1}")

    style = TableStyleInfo(
        name="TableStyleMedium9",
        showFirstColumn=False,
        showLastColumn=False,
        showRowStripes=True,
        showColumnStripes=True,
    )
    tab.tableStyleInfo = style
    ws.add_table(tab)

    # save to temp file for Django to send in response
    with NamedTemporaryFile() as tmp:
        wb.save(tmp.name)
        tmp.seek(0)
        stream = tmp.read()

    response = HttpResponse(
        content=stream,
        content_type="application/ms-excel",
    )
    response["Content-Disposition"] = "attachment; filename=Timary-Audit-Activity.xlsx"
    return response
