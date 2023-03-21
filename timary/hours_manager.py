import zoneinfo

from django.db.models import CharField, Count, F, IntegerField, Q, Value
from django.db.models.functions import Cast, Concat
from django.utils import timezone

from timary.models import HoursLineItem, Invoice, InvoiceManager, MilestoneInvoice
from timary.querysets import HourStats
from timary.utils import get_users_localtime


class HoursManager:
    def __init__(self, user, month=None):
        self.user = user
        if month:
            self.hours = HoursLineItem.all_hours.for_month_range(user, month)
        else:
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
        latest_hour_tracked = self.hours.first()
        latest_date_tracked = (
            latest_hour_tracked.date_tracked if latest_hour_tracked else None
        )
        if (
            isinstance(latest_hour_tracked, MilestoneInvoice)
            and latest_hour_tracked.invoice.milestone_completed
        ):
            latest_date_tracked = None
        if not latest_date_tracked:
            return show_repeat

        latest_date_tracked = latest_date_tracked.astimezone(
            tz=zoneinfo.ZoneInfo(self.user.timezone)
        ).date()
        users_localtime = get_users_localtime(self.user)
        if latest_date_tracked == users_localtime.date():
            show_repeat = 0
        elif (
            latest_date_tracked == (users_localtime - timezone.timedelta(days=1)).date()
        ):
            show_repeat = 1
        return show_repeat

    def filter_completed_milestones(self, hours):
        inv = Invoice.objects.get(id=hours["invoice"])
        return not (isinstance(inv, MilestoneInvoice) and inv.milestone_step)

    def show_most_frequent_options(self):
        """Get current months hours and get top 5 most frequent hours logged"""
        today = get_users_localtime(self.user)
        today_range = (
            today.replace(hour=0, minute=0, second=59),
            today.replace(hour=23, minute=59, second=59),
        )
        repeated_hours = (
            self.hours.filter(
                Q(recurring_logic__exact={}) | Q(recurring_logic__isnull=True)
            )
            .exclude(Q(invoice__is_paused=True) | Q(invoice__is_archived=True))
            .annotate(
                repeat_hours=Concat(
                    Cast(
                        Cast(F("quantity") * 100, output_field=IntegerField()),
                        output_field=CharField(),
                    ),
                    Value("_"),
                    "invoice__email_id",
                )
            )
            .values("repeat_hours")
            .annotate(repeat_hours_count=Count("repeat_hours"))
            .order_by("-repeat_hours_count")
            .values("quantity", "invoice__email_id", "invoice")
        )
        # Filter out milestones that have been completed
        repeated_hours = list(
            filter(
                self.filter_completed_milestones,
                repeated_hours,
            ),
        )

        repeated_hours_set = {
            (float(h["quantity"]), h["invoice__email_id"]) for h in repeated_hours[:5]
        }
        hours_today_set = {
            (float(h["quantity"]), h["invoice__email_id"])
            for h in self.hours.filter(date_tracked__range=today_range).values(
                "quantity", "invoice__email_id"
            )
        }
        hour_forms_to_offer = repeated_hours_set - hours_today_set
        return [
            {
                "quantity": hour[0],
                "invoice_name": InvoiceManager.fetch_by_email_id(
                    email_id=hour[1]
                ).title,
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
