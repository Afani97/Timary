import csv
import json
import zoneinfo
from calendar import HTMLCalendar
from datetime import datetime
from functools import reduce

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
    if user.timer_is_active is not None:
        running_times = (
            user.timer_is_active["running_times"]
            if "running_times" in user.timer_is_active
            else []
        )
        timer_running = user.timer_is_active["timer_running"]
        if timer_running:
            now = datetime.timestamp(datetime.now())
            running_times.append(now - int(user.timer_is_active["time_started"]))
        timer_ms = calculate_accumulative_time(running_times)
        context["active_timer_ms"] = timer_ms
        context["timer_running"] = timer_running
    return context


def calculate_accumulative_time(times):
    return reduce(lambda a, b: a + b, times, 0) * 1000


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
    if date.isoweekday() == 6:
        return date.date()
    return (date - timezone.timedelta(days=date.isoweekday())).date()


def get_date_parsed(date):
    return datetime.strftime(date, "%a").lower()


def get_users_localtime(user):
    return timezone.now().astimezone(tz=zoneinfo.ZoneInfo(user.timezone))


def generate_spreadsheet(response, user, year_date_range=None):
    from timary.models import SentInvoice

    sent_invoice_headers = [
        "Invoices sent",
        "Date Sent",
        "Date Paid",
        "Total Hours",
        "Total Price",
        "Paid Status",
    ]

    expense_headers = [
        "Expenses",
        "Description",
        "Date Tracked",
        "Cost",
    ]

    invoices = user.get_all_invoices()

    writer = csv.writer(response)

    for invoice in invoices:
        total_gross_profit = 0
        total_expenses_paid = 0
        writer.writerow([invoice.title])
        writer.writerow(sent_invoice_headers)

        sent_invoices = invoice.invoice_snapshots.all()
        if year_date_range:
            sent_invoices = sent_invoices.filter(date_paid__range=year_date_range)

        # add sent invoice data per row
        for sent_invoice in sent_invoices:
            total_hours = sent_invoice.invoice.line_items.aggregate(
                hours=Sum("quantity")
            )
            writer.writerow(
                [
                    "",
                    sent_invoice.date_sent.strftime("%Y-%m-%d"),
                    sent_invoice.date_paid.strftime("%Y-%m-%d")
                    if sent_invoice.date_paid
                    else "",
                    total_hours["hours"],
                    str(sent_invoice.total_price),
                    sent_invoice.get_paid_status_display(),
                ]
            )

            if sent_invoice.paid_status == SentInvoice.PaidStatus.PAID:
                total_gross_profit += float(sent_invoice.total_price)

        writer.writerow([""])
        writer.writerow(expense_headers)

        expenses = invoice.expenses.all()
        if year_date_range:
            expenses = expenses.filter(date_tracked__range=year_date_range)

        for expense in expenses:
            total_expenses_paid += float(expense.cost)
            writer.writerow(
                [
                    "",
                    expense.description,
                    expense.date_tracked.strftime("%Y-%m-%d"),
                    expense.cost,
                ]
            )

        writer.writerow([""])

        writer.writerow(["Gross Profit", "", "Total Expenses"])
        writer.writerow([total_gross_profit, "", total_expenses_paid])

        writer.writerow([""])
        writer.writerow([""])

    return response


class Calendar(HTMLCalendar):
    """Returns a calendar in html display dots for number of hours tracker per day + tooltip when hovering over item"""

    def __init__(self, user, date):
        self.user = user
        self.year = date.year
        self.month = date.month
        super(Calendar, self).__init__()

    def formatday(self, day, weekday, events):
        events_per_day = events.filter(date_tracked__day=day)
        d = ""
        for event in events_per_day:
            tooltip_class = "tooltip"
            if weekday <= 1:
                tooltip_class = "tooltip tooltip-right"
            elif weekday >= 5:
                tooltip_class = "tooltip tooltip-left"
            d += f"""
            <span class='{tooltip_class}' data-tip="{event.quantity}hrs for {event.invoice.title}">&#x2022;</span>
            """

        if day != 0:
            return f"<td><span class='date'>{day}</span><ul> {d} </ul></td>"
        return "<td></td>"

    def formatweek(self, theweek, events):
        week = ""
        for d, weekday in theweek:
            week += self.formatday(d, weekday, events)
        return f"<tr> {week} </tr>"

    def formatmonth(self, withyear=True):
        from timary.models import HoursLineItem

        events = HoursLineItem.objects.filter(
            date_tracked__year=self.year,
            date_tracked__month=self.month,
            invoice__user=self.user,
        ).select_related("invoice", "invoice__user")

        cal = '<table border="0" cellpadding="0" cellspacing="0" class="calendar">\n'
        cal += f"{self.formatmonthname(self.year, self.month, withyear=withyear)}\n"
        cal += f"{self.formatweekheader()}\n"
        for week in self.monthdays2calendar(self.year, self.month):
            cal += f"{self.formatweek(week, events)}\n"
        return cal
