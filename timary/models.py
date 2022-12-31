import datetime
import random
import uuid
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Count, F, Q, QuerySet, Sum, Value
from django.db.models.functions import Cast, Concat, TruncMonth
from django.template.loader import render_to_string
from django.utils.text import slugify
from django_q.tasks import async_task
from multiselectfield import MultiSelectField
from phonenumber_field.modelfields import PhoneNumberField

from timary.custom_errors import AccountingError
from timary.querysets import HoursQuerySet
from timary.services.accounting_service import AccountingService
from timary.services.email_service import EmailService
from timary.services.stripe_service import StripeService
from timary.services.twilio_service import TwilioClient
from timary.utils import get_date_parsed, get_starting_week_from_date


def create_new_ref_number():
    return str(random.randint(1000000000, 9999999999))


def validate_less_than_24_hours(value):
    if value > 24:
        raise ValidationError("Cannot log greater than 24 hours")


def validate_greater_than_zero_hours(value):
    if value < 0:
        raise ValidationError("Cannot log less than 0 hours")


class BaseModel(models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Contract(BaseModel):
    email = models.CharField(max_length=200, null=True, blank=True)
    name = models.CharField(max_length=200, null=True, blank=True)


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

    sent_invoice_id = models.CharField(max_length=200, null=True, blank=True)
    recurring_logic = models.JSONField(blank=True, null=True, default=dict)

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

    def is_recurring_date_today(self):
        """
        Checks if recurring_logic has a 'type' either 'recurring' or 'repeating'

        - If 'repeating': Check if today is end_date, then cancel recurring
        - Otherwise the rest are the same logic.
            - If daily, return true
            - If weekly or bi-weekly, check if the current week is valid,
                - If so, then check if current day is chosen

        - Return false otherwise
        """
        today = date.today()
        if (
            not self.recurring_logic
            or "type" not in self.recurring_logic
            or self.recurring_logic["type"]
            not in [
                "repeating",
                "recurring",
            ]
        ):
            return False
        if self.recurring_logic["type"] == "repeating":
            if datetime.date.fromisoformat(self.recurring_logic["end_date"]) <= today:
                self.cancel_recurring_hour()
                return False

        if self.recurring_logic["interval"] == "d":
            return True

        if self.recurring_logic["interval"] in ["w", "b"]:
            starting_week = date.fromisoformat(self.recurring_logic["starting_week"])
            if starting_week == get_starting_week_from_date(today):
                if get_date_parsed(today) in self.recurring_logic["interval_days"]:
                    return True

        return False

    def update_recurring_starting_weeks(self):
        """When on a saturday, after hours have been recorded,
        update starting weeks for new week
        """
        if "starting_week" in self.recurring_logic:
            num_weeks = 1 if self.recurring_logic["interval"] != "b" else 2
            self.recurring_logic["starting_week"] = date.fromisoformat(
                self.recurring_logic["starting_week"]
            ) + datetime.timedelta(weeks=num_weeks)
            self.save()

    def cancel_recurring_hour(self):
        self.recurring_logic = None
        self.save()


class Invoice(BaseModel):
    class InvoiceType(models.IntegerChoices):
        INTERVAL = 1, "INTERVAL"
        MILESTONE = 2, "MILESTONE"
        WEEKLY = 3, "WEEKLY"

    class Interval(models.TextChoices):
        DAILY = "D", "DAILY"
        WEEKLY = "W", "WEEKLY"
        BIWEEKLY = "B", "BIWEEKLY"
        MONTHLY = "M", "MONTHLY"
        QUARTERLY = "Q", "QUARTERLY"
        YEARLY = "Y", "YEARLY"

    invoice_type = models.IntegerField(
        default=InvoiceType.INTERVAL, choices=InvoiceType.choices
    )

    email_id = models.CharField(
        max_length=10, null=False, unique=True, default=create_new_ref_number
    )

    title = models.CharField(max_length=200)
    description = models.CharField(max_length=2000, null=True, blank=True)
    user = models.ForeignKey(
        "timary.User", on_delete=models.CASCADE, related_name="invoices", null=True
    )
    invoice_rate = models.DecimalField(
        default=100,
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(1)],
    )
    email_recipient_name = models.CharField(max_length=200, null=False, blank=False)
    email_recipient = models.EmailField(null=False, blank=False)
    email_recipient_stripe_customer_id = models.CharField(
        max_length=200, null=True, blank=True
    )

    invoice_interval = models.CharField(
        max_length=1,
        choices=Interval.choices,
        default=Interval.MONTHLY,
        blank=True,
        null=True,
    )
    milestone_total_steps = models.IntegerField(null=True, blank=True)
    milestone_step = models.IntegerField(default=1, null=True, blank=True)
    next_date = models.DateField(null=True, blank=True)
    last_date = models.DateField(null=True, blank=True)
    is_paused = models.BooleanField(default=False, null=True, blank=True)
    is_archived = models.BooleanField(default=False, null=True, blank=True)
    total_budget = models.IntegerField(null=True, blank=True)

    # Accounting
    accounting_customer_id = models.CharField(max_length=200, null=True, blank=True)

    def __str__(self):
        return f"{self.title}"

    def __repr__(self):
        return (
            f"Invoice(title={self.title}, "
            f"email_id={self.email_id}, "
            f"user={self.user}, "
            f"invoice_rate={self.invoice_rate}, "
            f"email_recipient={self.email_recipient}, "
            f"invoice_interval={self.invoice_interval}, "
            f"next_date={self.next_date}, "
            f"last_date={self.last_date}, "
            f"is_archived={self.is_archived})"
        )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def slug_title(self):
        return f"{slugify(self.title)}"

    def get_hours_tracked(self):
        return (
            self.hours_tracked.filter(
                date_tracked__gte=self.last_date, sent_invoice_id__isnull=True
            )
            .exclude(hours=0)
            .order_by("date_tracked")
        )

    def budget_percentage(self):
        if not self.total_budget:
            return 0

        if self.invoice_type == Invoice.InvoiceType.WEEKLY and self.total_budget:
            total_price = self.invoice_snapshots.filter(
                paid_status=SentInvoice.PaidStatus.PAID
            ).aggregate(total_cost=Sum("total_price"))
            if total_cost := total_price["total_cost"]:
                return (
                    round(
                        float(total_cost) / float(self.total_budget),
                        ndigits=2,
                    )
                    * 100
                )
            else:
                return 0

        total_hours = self.hours_tracked.filter(
            date_tracked__lte=datetime.date.today()
        ).aggregate(total_hours=Sum("hours"))
        total_cost_amount = 0
        if total_hours["total_hours"]:
            total_cost_amount = total_hours["total_hours"] * self.invoice_rate

        return round((total_cost_amount / self.total_budget), ndigits=2) * 100

    def get_last_six_months(self):
        today = datetime.date.today()
        date_times = [
            (today - relativedelta(months=m)).replace(day=1) for m in range(0, 6)
        ]
        six_months_qs = (
            self.invoice_snapshots.annotate(month=TruncMonth("date_sent"))
            .distinct()
            .values("month")
            .order_by("month")
            .annotate(totals=Sum("total_price"))
            .values("month", "totals")
        )
        months = []
        totals = []
        for m in date_times:
            datum = list(filter(lambda x: m == x["month"], six_months_qs))
            months.insert(0, m.strftime("%b"))
            total_count = float(datum[0]["totals"]) if datum else 0
            totals.insert(0, total_count)
        return months, totals

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
        todays_date = date.today()
        self.next_date = todays_date + self.get_next_date()
        if update_last:
            self.last_date = todays_date
        self.save()

    def increase_milestone_step(self):
        if self.invoice_type == Invoice.InvoiceType.MILESTONE:
            self.milestone_step += 1
            self.save()

    def get_hours_stats(self, date_range=None):
        query = Q(date_tracked__gte=self.last_date)
        if date_range:
            query = Q(date_tracked__range=date_range)
            pass
        hours_tracked = (
            self.hours_tracked.filter(query & Q(sent_invoice_id__isnull=True))
            .exclude(hours=0)
            .annotate(cost=self.invoice_rate * Sum("hours"))
            .order_by("date_tracked")
        )
        total_hours = hours_tracked.aggregate(total_hours=Sum("hours"))
        total_cost_amount = 0
        if (
            total_hours["total_hours"]
            and self.invoice_type != Invoice.InvoiceType.WEEKLY
        ):
            total_cost_amount = total_hours["total_hours"] * self.invoice_rate
        elif self.invoice_type == Invoice.InvoiceType.WEEKLY:
            total_cost_amount = self.invoice_rate

        return hours_tracked, total_cost_amount

    def sync_customer(self):
        if not self.email_recipient_stripe_customer_id:
            StripeService.create_customer_for_invoice(self)

        if not self.user.accounting_org_id:
            return None, None
        try:
            AccountingService({"user": self.user, "invoice": self}).create_customer()
        except AccountingError as ae:
            error_reason = ae.log()
            return False, error_reason  # Failed to sync customer
        return True, None  # Customer synced


class SentInvoice(BaseModel):
    class PaidStatus(models.IntegerChoices):
        NOT_STARTED = 0, "NOT_STARTED"
        PENDING = 1, "PENDING"
        PAID = 2, "PAID"
        FAILED = 3, "FAILED"

    hours_start_date = models.DateField(
        null=True, blank=True
    )  # Starting date of hours tracked
    hours_end_date = models.DateField(
        null=True, blank=True
    )  # Ending date of hours tracked
    date_sent = models.DateField(null=False, blank=False)
    invoice = models.ForeignKey(
        "timary.Invoice",
        on_delete=models.SET_NULL,
        related_name="invoice_snapshots",
        null=True,
        blank=True,
    )

    user = models.ForeignKey(
        "timary.User", on_delete=models.CASCADE, related_name="sent_invoices"
    )
    total_price = models.DecimalField(
        default=0,
        max_digits=9,
        decimal_places=2,
    )
    paid_status = models.PositiveSmallIntegerField(
        default=PaidStatus.NOT_STARTED, choices=PaidStatus.choices
    )
    stripe_payment_intent_id = models.CharField(max_length=200, blank=True, null=True)

    # Accounting
    accounting_invoice_id = models.CharField(max_length=200, blank=True, null=True)

    def __str__(self):
        return (
            f"SentInvoice(invoice={self.invoice.title if self.invoice else 'Deleted Invoice'}, "
            f"start_date={self.hours_start_date}, "
            f"end_date={self.hours_end_date}, "
            f"total_price={self.total_price}, "
            f"paid_status={self.get_paid_status_display()})"
        )

    def __repr__(self):
        return (
            f"SentInvoice(invoice={self.invoice}, "
            f"start_date={self.hours_start_date}, "
            f"end_date={self.hours_end_date}, "
            f"total_price={self.total_price}, "
            f"paid_status={self.get_paid_status_display()})"
        )

    @classmethod
    def create(cls, invoice):
        hours_tracked, total_cost = invoice.get_hours_stats()
        first_date_tracked = (
            hours_tracked.first().date_tracked if hours_tracked.first() else None
        )
        last_date_tracked = (
            hours_tracked.last().date_tracked if hours_tracked.last() else None
        )
        return SentInvoice.objects.create(
            hours_start_date=first_date_tracked,
            hours_end_date=last_date_tracked,
            date_sent=datetime.date.today(),
            invoice=invoice,
            user=invoice.user,
            total_price=total_cost,
        )

    @property
    def email_id(self):
        return f"{str(self.id).split('-')[0]}"

    def get_hours_tracked(self):
        hours_tracked = (
            self.invoice.hours_tracked.filter(sent_invoice_id=self.id)
            .exclude(hours=0)
            .order_by("date_tracked")
        )
        if self.invoice.invoice_type == Invoice.InvoiceType.WEEKLY:
            return hours_tracked, self.total_price

        total_hours = hours_tracked.aggregate(total_hours=Sum("hours"))
        total_cost_amount = 0
        if total_hours["total_hours"]:
            invoice_rate = round(self.total_price / total_hours["total_hours"], 1)
            total_cost_amount = total_hours["total_hours"] * invoice_rate
            hours_tracked = hours_tracked.annotate(cost=invoice_rate * F("hours"))

        return hours_tracked, total_cost_amount

    def success_notification(self):
        """
        1) Sends a notification using Twilio to user, if phone number is found
        2) Sends email receipt to invoice recipient
        3) Pushes updates to available accounting services.
        """
        TwilioClient.sent_payment_success(self)

        hours_tracked, _ = self.get_hours_tracked()

        msg_body = render_to_string(
            "email/sent_invoice_email.html",
            {
                "can_accept_payments": False,
                "user_name": self.user.invoice_branding_properties()["user_name"],
                "total_amount": self.total_price,
                "sent_invoice_id": self.id,
                "invoice": self.invoice,
                "hours_tracked": hours_tracked,
                "todays_date": self.date_sent,
                "invoice_branding": self.user.invoice_branding_properties(),
            },
        )
        EmailService.send_html(
            f"Here is a receipt for {self.invoice.user.first_name}'s services for {self.invoice.title}",
            msg_body,
            self.invoice.email_recipient,
        )
        EmailService.send_plain(
            "Success! Your getting paid!",
            f"""
Your recent invoice (#{self.email_id}) has been processed for payment.

You should receive your funds as soon as it has finished, usually within a few days.

Thanks again for using Timary,
Ari
ari@usetimary.com
            """,
            self.user.email,
        )

        if self.user.accounting_org_id:
            try:
                AccountingService(
                    {"user": self.user, "sent_invoice": self}
                ).create_invoice()
            except AccountingError as ae:
                ae.log()

    @property
    def is_synced(self):
        return (
            self.paid_status == SentInvoice.PaidStatus.PAID
            and self.accounting_invoice_id is not None
            and self.invoice.accounting_customer_id is not None
        )

    @property
    def can_be_synced(self):
        return (
            self.user.accounting_org_id is not None
            and self.paid_status == SentInvoice.PaidStatus.PAID
            and self.accounting_invoice_id is None
            and self.invoice.accounting_customer_id is not None
            and self.user.settings["subscription_active"]
        )

    def sync_invoice(self):
        if self.paid_status != SentInvoice.PaidStatus.PAID:
            return None, "Invoice isn't paid"

        if not self.user.accounting_org_id:
            return None, "No accounting service found"

        try:
            AccountingService(
                {"user": self.user, "sent_invoice": self}
            ).create_invoice()
        except AccountingError as ae:
            error_reason = ae.log()
            return False, error_reason
        return True, None


class User(AbstractUser, BaseModel):
    class StripeConnectDisabledReasons(models.IntegerChoices):
        NONE = 1, "NONE"
        PENDING = 2, "PENDING"
        MORE_INFO = 3, "MORE_INFO"

    class StripeSubscriptionStatus(models.IntegerChoices):
        TRIAL = 1, "TRIAL"
        ACTIVE = 2, "ACTIVE"
        INACTIVE = 3, "INACTIVE"

    stripe_customer_id = models.CharField(max_length=200, null=True, blank=True)
    stripe_payouts_enabled = models.BooleanField(default=False)
    stripe_connect_id = models.CharField(max_length=200, null=True, blank=True)
    stripe_subscription_id = models.CharField(max_length=200, null=True, blank=True)
    stripe_connect_reason = models.IntegerField(
        default=StripeConnectDisabledReasons.MORE_INFO,
        choices=StripeConnectDisabledReasons.choices,
    )
    stripe_subscription_status = models.IntegerField(
        default=StripeSubscriptionStatus.TRIAL, choices=StripeSubscriptionStatus.choices
    )

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
    phone_number_repeat_sms = models.BooleanField(default=False)

    # Accounting integration
    accounting_org = models.CharField(max_length=200, blank=True, null=True)
    accounting_org_id = models.CharField(max_length=200, null=True, blank=True)
    accounting_refresh_token = models.CharField(max_length=200, blank=True, null=True)

    profile_pic = models.ImageField(upload_to="profile_pics/", null=True, blank=True)

    # Custom invoice branding
    invoice_branding = models.JSONField(blank=True, null=True, default=dict)

    # Invite referral id
    referrer_id = models.CharField(
        max_length=10, unique=True, default=create_new_ref_number
    )

    # Keep track of active timer
    timer_is_active = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.username})"

    def __repr__(self):
        return f"{self.first_name} {self.last_name} ({self.username})"

    @property
    def settings(self):
        return {
            "accounting_connected": self.get_accounting_connected,
            "phone_number_availability": self.phone_number_availability,
            "subscription_active": self.subscription_is_active,
        }

    @property
    def get_invoices(self):
        return self.invoices.filter(is_archived=False)

    @property
    def subscription_is_active(self):
        return self.stripe_subscription_status in [
            User.StripeSubscriptionStatus.TRIAL,
            User.StripeSubscriptionStatus.ACTIVE,
        ]

    def get_all_invoices(self):
        return self.invoices.all()

    def invoices_not_logged(self):
        invoices = set(
            self.get_invoices.filter(
                Q(is_paused=False) & Q(hours_tracked__date_tracked__exact=date.today())
            )
        )
        remaining_invoices = set(self.get_invoices.filter(is_paused=False)) - invoices
        if len(remaining_invoices) > 0:
            return remaining_invoices

    @property
    def formatted_phone_number(self):
        return f"+{self.phone_number.country_code}{self.phone_number.national_number}"

    @property
    def get_accounting_connected(self):
        if self.accounting_org_id:
            return self.accounting_org

    @property
    def can_accept_payments(self):
        return self.stripe_payouts_enabled and self.settings["subscription_active"]

    def user_referred(self):
        if not self.settings["subscription_active"]:
            return
        subscription = StripeService.get_subscription(self.stripe_subscription_id)
        amount = 500  # $5
        if subscription["discount"]:
            # If a biz already has a discount applied to their account, max out the coupon to $10
            if subscription["discount"]["coupon"]["amount_off"] == amount:
                amount = 1000
                return StripeService.create_subscription_discount(
                    self, amount, subscription["id"]
                )

        else:
            return StripeService.create_subscription_discount(self, amount)

    def can_repeat_previous_hours_logged(self, hours: QuerySet):
        """
        :param hours:
        :return: show_repeat:
            0 == Don't show any message
            1 == Show button to repeat
            2 == Show message to log hours (no hours logged day before)
        """
        show_repeat = 2
        latest_hour_tracked = hours.order_by("-date_tracked").first()
        latest_date_tracked = (
            latest_hour_tracked.date_tracked if latest_hour_tracked else None
        )
        if latest_date_tracked == datetime.date.today():
            show_repeat = 0
        elif latest_date_tracked == (
            datetime.date.today() - datetime.timedelta(days=1)
        ):
            show_repeat = 1
        return show_repeat

    def show_most_frequent_options(self, hours: QuerySet):
        """Get current months hours and get top 3 most frequent hours logged"""
        today = date.today()
        repeated_hours = (
            hours.filter(Q(recurring_logic__exact={}) | Q(recurring_logic__isnull=True))
            .annotate(
                repeat_hours=Concat(
                    Cast(
                        Cast(F("hours") * 100, output_field=models.IntegerField()),
                        output_field=models.CharField(),
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
            for h in hours.filter(date_tracked=today).values(
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

    def invoice_branding_properties(self):
        return {
            "due_date_selected": self.invoice_branding.get("due_date"),
            "next_weeks_date": datetime.date.today()
            + datetime.timedelta(weeks=int(self.invoice_branding.get("due_date") or 1)),
            "user_name": self.invoice_branding.get("company_name") or self.first_name,
            "hide_timary": self.invoice_branding.get("hide_timary") or False,
            "show_profile_pic": self.invoice_branding.get("show_profile_pic"),
            "profile_pic": self.profile_pic,
            "personal_website": self.invoice_branding.get("personal_website") or "",
            "linked_in": self.invoice_branding.get("linked_in") or "",
            "twitter": self.invoice_branding.get("twitter") or "",
            "youtube": self.invoice_branding.get("youtube") or "",
        }

    def update_payouts_enabled(self, reason):
        if not reason:
            self.stripe_payouts_enabled = True
            self.stripe_connect_reason = User.StripeConnectDisabledReasons.NONE
        elif reason in ["requirements.pending_verification", "under_review"]:
            self.stripe_payouts_enabled = False
            self.stripe_connect_reason = User.StripeConnectDisabledReasons.PENDING
        elif reason in ["requirements.past_due", "rejected.other", "other"]:
            self.stripe_payouts_enabled = False
            self.stripe_connect_reason = User.StripeConnectDisabledReasons.MORE_INFO
        self.save()

    def onboard_user(self):
        """Don't block the main process for these tasks"""
        _ = async_task(
            "timary.services.stripe_service.StripeService.create_new_subscription", self
        )

        _ = async_task(
            "timary.services.email_service.EmailService.send_plain",
            "Welcome to Timary!",
            f"""
Hi {self.first_name},

I want to personally thank you for joining Timary.

It's not everyday that someone signs up for a new service.
I'm glad to see you've chosen my app to help alleviate some of your difficulties.

As will most products, Timary will improve with time and that can happen a lot faster if you help out!
Please do not hesitate to email me with any pain points you run into while using the app.
Any and all feedback is welcome!

I really appreciate for the opportunity to work with you,
Aristotel F
Timary

        """,
            self.email,
        )
