import calendar
import zoneinfo
from datetime import timedelta

from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone

from timary.utils import get_users_localtime


class HoursQuerySet(models.QuerySet):
    def current_month(self, user):
        beginning_of_month = get_users_localtime(user).replace(
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
            tzinfo=zoneinfo.ZoneInfo(user.timezone),
        )
        return (
            self.filter(
                invoice__user=user,
                invoice__is_archived=False,
                date_tracked__gte=beginning_of_month,
            )
            .exclude(quantity=0)
            .select_related("invoice", "invoice__user")
            .order_by("-date_tracked")
        )

    def for_month_range(self, user, month):
        last_day = calendar.monthrange(month.year, month.month)[1]
        month_range = (
            month.replace(
                day=1,
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
                tzinfo=zoneinfo.ZoneInfo(user.timezone),
            ),
            month.replace(
                day=last_day,
                hour=23,
                minute=59,
                second=59,
                microsecond=59,
                tzinfo=zoneinfo.ZoneInfo(user.timezone),
            ),
        )
        return (
            self.filter(
                invoice__user=user,
                invoice__is_archived=False,
                date_tracked__range=month_range,
            )
            .exclude(quantity=0)
            .select_related("invoice", "invoice__user")
            .order_by("-date_tracked")
        )


def get_last_month(tz):
    """Easier for testing"""
    return (
        timezone.now().astimezone(tz=tz).replace(day=1) - timezone.timedelta(days=1)
    ).replace(day=1, hour=0, minute=0, second=0, microsecond=0, tzinfo=tz)


class HourStats:
    def __init__(self, user):
        self.user = user
        tz = zoneinfo.ZoneInfo(self.user.timezone)
        self.current_month = timezone.now().astimezone(tz=tz)
        self.last_month = get_last_month(tz)
        self.first_month = timezone.now().astimezone(tz=tz).replace(month=1)

    def get_sent_invoices_stats(self, date_range=None):
        from timary.models import HoursLineItem, SentInvoice

        sent_invoices = self.user.sent_invoices.filter(
            date_sent__range=date_range
        ).exclude(
            Q(paid_status=SentInvoice.PaidStatus.FAILED)
            | Q(paid_status=SentInvoice.PaidStatus.CANCELLED)
        )

        total_hours = HoursLineItem.objects.filter(
            sent_invoice_id__in=map(str, sent_invoices.values_list("id", flat=True)),
            date_tracked__range=date_range,
        ).aggregate(total_hours=Sum("quantity"))["total_hours"]
        total_amount = sent_invoices.aggregate(total_amount=Sum("total_price"))[
            "total_amount"
        ]

        return total_hours or 0, total_amount or 0

    def get_untracked_hour_stats(self, date_range=None):
        from timary.models import HoursLineItem

        qs = (
            HoursLineItem.objects.filter(
                invoice__user=self.user,
                sent_invoice_id__isnull=True,
                date_tracked__range=date_range,
            )
            .exclude(quantity=0)
            .prefetch_related("invoice")
            .order_by("-date_tracked")
        )

        total_hours_sum = qs.aggregate(total_hours=Sum("quantity"))["total_hours"]
        total_amount = 0
        for line_item in qs.all():
            if line_item.invoice.invoice_type() != "weekly":
                total_amount += line_item.quantity * line_item.invoice.rate

        return total_hours_sum or 0, total_amount or 0

    def get_stats(self, date_range=None):
        sent_invoice_stats = self.get_sent_invoices_stats(date_range)
        hour_stats = self.get_untracked_hour_stats(date_range)
        return {
            "total_hours": sent_invoice_stats[0] + hour_stats[0],
            "total_amount": sent_invoice_stats[1] + hour_stats[1],
        }

    def get_current_month_stats(self):
        return self.get_stats(
            (
                self.current_month.replace(
                    day=1, hour=0, minute=0, second=0, microsecond=0
                ),
                self.current_month,
            )
        )

    def get_last_month_stats(self):
        date_range = (
            self.last_month,
            self.current_month.replace(day=1) - timedelta(days=1),
        )
        return self.get_stats(date_range)
