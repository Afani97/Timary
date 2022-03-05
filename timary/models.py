import random
import uuid
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q, Sum
from django.utils.text import slugify
from django.utils.timezone import localtime, now
from multiselectfield import MultiSelectField
from phonenumber_field.modelfields import PhoneNumberField

from timary.querysets import HoursQuerySet


def create_new_ref_number():
    return str(random.randint(1000000000, 9999999999))


def validate_less_than_24_hours(value):
    if value > 23.5:
        raise ValidationError(f"{value} cannot be greater than 24 hours")


def validate_greater_than_zero_hours(value):
    if value < 0:
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
        max_digits=4,
        decimal_places=2,
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

    # Quickbooks
    quickbooks_customer_ref_id = models.CharField(max_length=200, null=True, blank=True)

    # Freshbooks
    freshbooks_client_id = models.CharField(max_length=200, null=True, blank=True)

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

    @property
    def get_hours_tracked(self):
        return self.hours_tracked.filter(
            date_tracked__gte=F("invoice__last_date")
        ).order_by("date_tracked")

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

    def get_hours_stats(self, date_range=None):
        query = Q(date_tracked__gte=F("invoice__last_date"))
        if date_range:
            query = Q(date_tracked__range=date_range)
            pass
        hours_tracked = (
            self.hours_tracked.filter(query)
            .annotate(cost=F("invoice__hourly_rate") * Sum("hours"))
            .order_by("date_tracked")
        )
        total_hours = hours_tracked.aggregate(total_hours=Sum("hours"))
        total_cost_amount = 0
        if total_hours["total_hours"]:
            total_cost_amount = total_hours["total_hours"] * self.hourly_rate

        return hours_tracked, total_cost_amount


class SentInvoice(BaseModel):
    class PaidStatus(models.IntegerChoices):
        PENDING = 1, "PENDING"
        PAID = 2, "PAID"

    hours_start_date = models.DateField(
        null=True, blank=True
    )  # Starting date of hours tracked
    hours_end_date = models.DateField(
        null=True, blank=True
    )  # Ending date of hours tracked
    date_sent = models.DateField(null=False, blank=False)
    invoice = models.ForeignKey(
        "timary.Invoice", on_delete=models.CASCADE, related_name="invoice_snapshots"
    )

    user = models.ForeignKey(
        "timary.User", on_delete=models.CASCADE, related_name="sent_invoices"
    )
    total_price = models.PositiveIntegerField()
    paid_status = models.PositiveSmallIntegerField(
        default=PaidStatus.PENDING, choices=PaidStatus.choices
    )

    # Quickbooks
    quickbooks_invoice_id = models.CharField(max_length=200, blank=True, null=True)

    # Freshbooks
    freshbooks_invoice_id = models.CharField(max_length=200, blank=True, null=True)

    def __str__(self):
        return (
            f"SentInvoice(invoice={self.invoice.title}, "
            f"start_date={self.hours_start_date}, "
            f"end_date={self.hours_end_date}, "
            f"total_price={self.total_price}, "
            f"paid_status={self.get_paid_status_display()})"
        )

    def __repr__(self):
        return (
            f"SentInvoice(invoice={self.invoice.title}, "
            f"start_date={self.hours_start_date}, "
            f"end_date={self.hours_end_date}, "
            f"total_price={self.total_price}, "
            f"paid_status={self.get_paid_status_display()})"
        )

    def get_hours_tracked(self):
        return (
            self.invoice.hours_tracked.filter(
                date_tracked__range=[
                    self.hours_start_date,
                    self.hours_end_date,
                ]
            )
            .annotate(cost=F("invoice__hourly_rate") * Sum("hours"))
            .order_by("date_tracked")
        )


class User(AbstractUser, BaseModel):
    class MembershipTier(models.IntegerChoices):
        STARTER = 5, "STARTER"
        PROFESSIONAL = 19, "PROFESSIONAL"
        BUSINESS = 49, "BUSINESS"

    membership_tier = models.PositiveSmallIntegerField(
        default=MembershipTier.STARTER,
        choices=MembershipTier.choices,
        blank=False,
    )
    stripe_customer_id = models.CharField(max_length=200, null=True, blank=True)
    stripe_payouts_enabled = models.BooleanField(default=False)
    stripe_connect_id = models.CharField(max_length=200, null=True, blank=True)
    stripe_subscription_id = models.CharField(max_length=200, null=True, blank=True)

    WEEK_DAYS = (
        ("Mon", "Mon"),
        ("Tue", "Tue"),
        ("Wed", "Wed"),
        ("Thu", "Thu"),
        ("Fri", "Fri"),
        ("Sat", "Sat"),
        ("Sun", "Sun"),
    )
    phone_number = PhoneNumberField(unique=True, blank=True, null=True)
    phone_number_availability = MultiSelectField(
        choices=WEEK_DAYS, null=True, blank=True
    )

    # Quickbooks integration id
    quickbooks_realm_id = models.CharField(max_length=200, null=True, blank=True)

    # Freshbooks integration id
    freshbooks_account_id = models.CharField(max_length=200, null=True, blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.username})"

    def __repr__(self):
        return f"{self.first_name} {self.last_name} ({self.username})"

    @property
    def settings(self):
        return {
            "phone_number_availability": self.phone_number_availability,
            "quickbooks_connected": self.quickbooks_realm_id is not None,
            "freshbooks_connected": self.freshbooks_account_id is not None,
            "zoho_connected": False,
            "xero_connected": False,
        }

    @property
    def invoices_not_logged(self):
        invoices = set(
            self.invoices.filter(
                Q(next_date__isnull=False)
                & Q(hours_tracked__date_tracked__exact=date.today())
            )
        )
        remaining_invoices = (
            set(self.invoices.filter(next_date__isnull=False)) - invoices
        )
        return remaining_invoices

    @property
    def formatted_phone_number(self):
        return f"+{self.phone_number.country_code}{self.phone_number.national_number}"

    @property
    def can_accept_payments(self):
        return self.stripe_payouts_enabled and self.can_receive_texts

    @property
    def can_receive_texts(self):
        return (
            self.membership_tier == User.MembershipTier.PROFESSIONAL
            or self.membership_tier == User.MembershipTier.BUSINESS
        )

    @property
    def can_create_invoices(self):
        invoices_count = self.invoices.count()
        if invoices_count == 0:
            # Empty state
            return False
        if self.membership_tier == User.MembershipTier.STARTER:
            return False
        elif self.membership_tier == User.MembershipTier.PROFESSIONAL:
            return invoices_count <= 1
        elif self.membership_tier == User.MembershipTier.BUSINESS:
            return True
        else:
            return False


class QuickbooksOAuth(BaseModel):
    """Keep track of refresh_token from QuickBooks OAuth so re-auth does not need to happen again."""

    refresh_token = models.CharField(max_length=200, blank=True, null=True)


class FreshbooksOAuth(BaseModel):
    """Keep track of refresh_token from Freshbooks OAuth so re-auth does not need to happen again."""

    refresh_token = models.CharField(max_length=200, blank=True, null=True)
