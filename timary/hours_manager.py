from datetime import date, timedelta

from django.db.models import CharField, Count, F, IntegerField, Q, Value
from django.db.models.functions import Cast, Concat

from timary.models import HoursLineItem, Invoice
from timary.querysets import HourStats


class HoursManager:
    def __init__(self, user):
        self.user = user
        self.hours = HoursLineItem.all_hours.current_month(user)

    def can_repeat_previous_hours_logged(self):
        """
        :param hours:
        :return: show_repeat:
            0 == Don't show any message
            1 == Show button to repeat
            2 == Show message to log hours (no hours logged day before)
        """
        show_repeat = 2
        latest_hour_tracked = self.hours.order_by("-date_tracked").first()
        latest_date_tracked = (
            latest_hour_tracked.date_tracked if latest_hour_tracked else None
        )
        if latest_date_tracked == date.today():
            show_repeat = 0
        elif latest_date_tracked == (date.today() - timedelta(days=1)):
            show_repeat = 1
        return show_repeat

    def show_most_frequent_options(self):
        """Get current months hours and get top 3 most frequent hours logged"""
        today = date.today()
        repeated_hours = (
            self.hours.filter(
                Q(recurring_logic__exact={}) | Q(recurring_logic__isnull=True)
            )
            .annotate(
                repeat_hours=Concat(
                    Cast(
                        Cast(F("hours") * 100, output_field=IntegerField()),
                        output_field=CharField(),
                    ),
                    Value("_"),
                    "invoice__email_id",
                )
            )
            .values("repeat_hours")
            .annotate(repeat_hours_count=Count("repeat_hours"))
            .order_by("-repeat_hours_count")[:5]
            .values("hours", "invoice__email_id")
        )
        repeated_hours_set = {
            (float(h["hours"]), h["invoice__email_id"]) for h in repeated_hours
        }
        hours_today_set = {
            (float(h["hours"]), h["invoice__email_id"])
            for h in self.hours.filter(date_tracked=today).values(
                "hours", "invoice__email_id"
            )
        }
        hour_forms_to_offer = repeated_hours_set - hours_today_set
        return [
            {
                "hours": hour[0],
                "invoice_name": Invoice.objects.get(email_id=hour[1]).title,
                "invoice_reference_id": f"{hour[0]}_{hour[1]}",
            }
            for hour in hour_forms_to_offer
        ]

    def get_hours_tracked(self):
        hour_stats = HourStats(user=self.user)
        context = {
            "current_month": hour_stats.get_current_month_stats(),
            "last_month": hour_stats.get_last_month_stats(),
            "current_year": hour_stats.get_this_year_stats(),
        }
        return context
