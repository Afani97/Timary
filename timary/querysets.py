from datetime import datetime

from dateutil import relativedelta
from django.db import models


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
            .exclude(hours=0)
            .select_related("invoice")
            .order_by("-date_tracked")
        )

    def last_month(self, user):
        last_month = datetime.today() - relativedelta.relativedelta(months=1)
        current_date = datetime.today()
        return (
            self.filter(
                invoice__user=user,
                invoice__is_archived=False,
                date_tracked__month__gte=last_month.month,
                date_tracked__month__lt=current_date.month,
                date_tracked__year__gte=last_month.year,
                date_tracked__year__lte=current_date.year,
            )
            .exclude(hours=0)
            .select_related("invoice")
            .order_by("-date_tracked")
        )

    def current_year(self, user):
        current_date = datetime.today()
        return (
            self.filter(
                invoice__user=user,
                invoice__is_archived=False,
                date_tracked__month__gte=1,
                date_tracked__year__gte=current_date.year,
            )
            .exclude(hours=0)
            .select_related("invoice")
            .order_by("-date_tracked")
        )
