from datetime import date, datetime, timedelta

from dateutil import relativedelta
from django.db import models
from django.db.models import F, Sum


class HoursQuerySet(models.QuerySet):
    def current_month(self, user):
        current_date = datetime.today()
        return (
            self.filter(
                invoice__user=user,
                invoice__is_archived=False,
                date_tracked__month__gte=current_date.month,
                date_tracked__year__gte=current_date.year,
            )
            .exclude(quantity=0)
            .select_related("invoice", "invoice__user")
            .order_by("-date_tracked")
        )


class HourStats:
    def __init__(self, user):
        self.user = user
        self.current_month = datetime.today()
        self.last_month = (
            datetime.today() - relativedelta.relativedelta(months=1)
        ).replace(day=1)
        self.first_month = datetime.today().replace(month=1)

    def get_sent_invoices_stats(self, date_range=None):
        from timary.models import HoursLineItem, SentInvoice

        sent_invoices = self.user.sent_invoices.filter(
            date_sent__range=date_range
        ).exclude(paid_status=SentInvoice.PaidStatus.FAILED)

        total_hours = HoursLineItem.objects.filter(
            sent_invoice_id__in=map(str, sent_invoices.values_list("id", flat=True))
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
            .select_related("invoice")
            .order_by("-date_tracked")
        )

        total_hours_sum = qs.aggregate(total_hours=Sum("quantity"))["total_hours"]
        total_amount_sum_non_weekly_invoice = (
            qs.filter(invoice__invoice_type__lt=3)
            .annotate(total_amount=F("quantity") * F("invoice__invoice_rate"))
            .aggregate(total=Sum("total_amount"))["total"]
        )

        return total_hours_sum or 0, total_amount_sum_non_weekly_invoice or 0

    def get_stats(self, date_range=None):
        sent_invoice_stats = self.get_sent_invoices_stats(date_range)
        hour_stats = self.get_untracked_hour_stats(date_range)
        return {
            "total_hours": sent_invoice_stats[0] + hour_stats[0],
            "total_amount": sent_invoice_stats[1] + hour_stats[1],
        }

    def get_current_month_stats(self):
        return self.get_stats((self.current_month.replace(day=1), self.current_month))

    def get_last_month_stats(self):
        date_range = (
            self.last_month,
            (self.current_month.replace(day=1) - timedelta(days=1)),
        )
        return self.get_stats(date_range)

    def get_this_year_stats(self):
        date_range = (
            date(self.current_month.year, 1, 1),
            self.current_month,
        )
        return self.get_stats(date_range)
