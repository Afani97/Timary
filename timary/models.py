import random
import uuid
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.text import slugify
from django.utils.timezone import localtime, now

from timary.querysets import HoursQuerySet


def create_new_ref_number():
    return str(random.randint(1000000000, 9999999999))


def validate_less_than_24_hours(value):
    if value > 23.5:
        raise ValidationError(f"{value} cannot be greater than 24 hours")


def validate_greater_than_zero_hours(value):
    if value <= 0:
        raise ValidationError(f"{value} cannot be less than 0 hours")


class BaseModel(models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class DailyHoursInput(BaseModel):
    invoice = models.ForeignKey(
        "timary.Invoice", on_delete=models.CASCADE, related_name="hours_tracked"
    )
    hours = models.DecimalField(
        default=1,
        max_digits=3,
        decimal_places=1,
        validators=[validate_less_than_24_hours, validate_greater_than_zero_hours],
    )
    notes = models.CharField(max_length=2000, null=True, blank=True)
    date_tracked = models.DateField()

    objects = models.Manager()
    all_hours = HoursQuerySet.as_manager()

    def __str__(self):
        return f"{self.invoice.title} - {self.date_tracked} - {self.hours}"

    def __repr__(self):
        return (
            f"DailyHoursInput(invoice={self.invoice}, "
            f"hours={self.hours}, "
            f"date_tracked={self.date_tracked})"
        )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def slug_id(self):
        return f"{slugify(self.invoice.title)}-{str(self.id.int)[:6]}"


class Invoice(BaseModel):
    class Interval(models.TextChoices):
        DAILY = "D", "DAILY"
        WEEKLY = "W", "WEEKLY"
        BIWEEKLY = "B", "BIWEEKLY"
        MONTHLY = "M", "MONTHLY"
        QUARTERLY = "Q", "QUARTERLY"
        YEARLY = "Y", "YEARLY"

    email_id = models.CharField(
        max_length=10, null=False, unique=True, default=create_new_ref_number
    )

    title = models.CharField(max_length=200)
    description = models.CharField(max_length=2000, null=True, blank=True)
    user = models.ForeignKey(
        "timary.User", on_delete=models.CASCADE, related_name="invoices"
    )

    hourly_rate = models.IntegerField(
        default=50, null=False, blank=False, validators=[MinValueValidator(1)]
    )
    email_recipient_name = models.CharField(max_length=200, null=False, blank=False)
    email_recipient = models.EmailField(null=False, blank=False)

    invoice_interval = models.CharField(
        max_length=1, choices=Interval.choices, default=Interval.MONTHLY
    )
    next_date = models.DateField(null=True, blank=True)
    last_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.title}"

    def __repr__(self):
        return (
            f"Invoice(title={self.title}, "
            f"email_id={self.email_id}, "
            f"user={self.user}, "
            f"hourly_rate={self.hourly_rate}, "
            f"email_recipient={self.email_recipient}, "
            f"invoice_interval={self.invoice_interval}, "
            f"next_date={self.next_date}, "
            f"last_date={self.last_date})"
        )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def slug_title(self):
        return f"{slugify(self.title)}"

    def get_next_date(self):
        if self.invoice_interval == Invoice.Interval.DAILY:
            return timedelta(days=1)
        elif self.invoice_interval == Invoice.Interval.WEEKLY:
            return timedelta(weeks=1)
        elif self.invoice_interval == Invoice.Interval.BIWEEKLY:
            return timedelta(weeks=2)
        elif self.invoice_interval == Invoice.Interval.MONTHLY:
            return relativedelta(months=1)
        elif self.invoice_interval == Invoice.Interval.QUARTERLY:
            return relativedelta(months=3)
        else:
            return relativedelta(years=1)

    def calculate_next_date(self, update_last: bool = True):
        todays_date = localtime(now()).date()
        self.next_date = todays_date + self.get_next_date()
        if update_last:
            self.last_date = todays_date
        self.save()


class User(AbstractUser, BaseModel):
    phone_number = models.CharField(
        max_length=16,
        unique=True,
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.username})"

    def __repr__(self):
        return f"{self.first_name} {self.last_name} ({self.username})"

    @property
    def invoices_not_logged(self):
        invoices = set(
            self.invoices.filter(hours_tracked__date_tracked__exact=date.today())
        )
        remaining_invoices = set(self.invoices.all()) - invoices
        return remaining_invoices
