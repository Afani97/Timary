import random
import uuid
import zoneinfo
from datetime import date, datetime, timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import DateField, F, Q, Sum
from django.db.models.functions import TruncMonth
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.text import slugify
from django_q.tasks import async_task
from multiselectfield import MultiSelectField
from phonenumber_field.modelfields import PhoneNumberField
from polymorphic.models import PolymorphicModel

from timary.custom_errors import AccountingError
from timary.invoice_builder import InvoiceBuilder
from timary.querysets import HoursQuerySet
from timary.services.accounting_service import AccountingService
from timary.services.email_service import EmailService
from timary.services.stripe_service import StripeService
from timary.services.twilio_service import TwilioClient
from timary.utils import (
    get_date_parsed,
    get_starting_week_from_date,
    get_users_localtime,
)


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


class LineItem(PolymorphicModel, BaseModel):
    invoice = models.ForeignKey(
        "timary.Invoice", on_delete=models.CASCADE, related_name="line_items"
    )
    date_tracked = models.DateTimeField(null=True, blank=True)
    description = models.CharField(max_length=200, null=True, blank=True)
    quantity = models.DecimalField(
        default=1,
        max_digits=9,
        decimal_places=2,
    )
    unit_price = models.DecimalField(
        default=0,
        max_digits=9,
        decimal_places=2,
    )
    sent_invoice_id = models.CharField(max_length=200, null=True, blank=True)

    @property
    def slug_id(self):
        return f"{slugify(self.invoice.title)}-{str(self.id.int)[:6]}"

    def total_amount(self):
        return self.quantity * self.unit_price


class HoursLineItem(LineItem):
    recurring_logic = models.JSONField(blank=True, null=True, default=dict)

    objects = models.Manager()
    all_hours = HoursQuerySet.as_manager()

    def __str__(self):
        return f"{self.invoice.title} - {self.date_tracked} - {self.quantity}"

    def __repr__(self):
        return (
            f"HoursLineItem(invoice={self.invoice}, "
            f"hours={self.quantity}, "
            f"date_tracked={self.date_tracked})"
        )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

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
        today = timezone.now()
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
            if (
                datetime.fromisoformat(self.recurring_logic["end_date"]).date()
                <= today.date()
            ):
                self.cancel_recurring_hour()
                return False

        if self.recurring_logic["interval"] == "d":
            return True

        if self.recurring_logic["interval"] in ["w", "b"]:
            starting_week = datetime.fromisoformat(
                self.recurring_logic["starting_week"]
            ).date()
            if starting_week == get_starting_week_from_date(today):
                if (
                    get_date_parsed(today.date())
                    in self.recurring_logic["interval_days"]
                ):
                    return True

        return False

    def update_recurring_starting_weeks(self):
        """When on a saturday, after hours have been recorded,
        update starting weeks for new week
        """
        if "starting_week" in self.recurring_logic:
            num_weeks = 1 if self.recurring_logic["interval"] != "b" else 2
            self.recurring_logic["starting_week"] = (
                date.fromisoformat(self.recurring_logic["starting_week"])
                + timezone.timedelta(weeks=num_weeks)
            ).isoformat()
            self.save()

    def cancel_recurring_hour(self):
        self.recurring_logic = None
        self.save()


class Invoice(PolymorphicModel, BaseModel):
    title = models.CharField(max_length=200)
    description = models.CharField(max_length=2000, null=True, blank=True)
    user = models.ForeignKey(
        "timary.User", on_delete=models.CASCADE, related_name="invoices", null=True
    )
    rate = models.DecimalField(
        default=100,
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(1)],
        null=True,
        blank=True,
    )
    balance_due = models.DecimalField(
        default=100,
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
    )
    client_name = models.CharField(max_length=200, null=False, blank=False)
    client_email = models.EmailField(null=False, blank=False)
    client_stripe_customer_id = models.CharField(max_length=200, null=True, blank=True)

    email_id = models.CharField(
        max_length=10, null=False, unique=True, default=create_new_ref_number
    )
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
            f"invoice_rate={self.rate}, "
            f"client_email={self.client_email}, "
            f"is_archived={self.is_archived})"
        )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def slug_title(self):
        return f"{slugify(self.title)}"

    def invoice_type(self):
        raise NotImplementedError()

    def get_hours_stats(self):
        raise NotImplementedError()

    def render_line_items(self, sent_invoice_id):
        raise NotImplementedError()

    def update(self):
        raise NotImplementedError()

    def form_class(self, action="create"):
        raise NotImplementedError()

    def sync_customer(self):
        if not self.client_stripe_customer_id:
            StripeService.create_customer_for_invoice(self)

        if not self.user.accounting_org_id:
            return None, None

        if self.accounting_customer_id:
            return True, None
        try:
            AccountingService({"user": self.user, "invoice": self}).create_customer()
        except AccountingError as ae:
            error_reason = ae.log()
            return False, error_reason  # Failed to sync customer
        return True, None  # Customer synced

    def get_hours_sent(self, sent_invoice_id):
        return (
            self.line_items.filter(sent_invoice_id=sent_invoice_id)
            .exclude(quantity=0)
            .annotate(cost=self.rate * Sum("quantity"))
            .order_by("date_tracked")
        )

    def invoices_pending(self):
        if self.invoice_type() == "single":
            if self.installments == 0:
                return 0
        return self.invoice_snapshots.filter(
            Q(paid_status=0) | Q(paid_status=1)
        ).count()


class SingleInvoice(Invoice):
    class InvoiceStatus(models.IntegerChoices):
        DRAFT = 0, "DRAFT"
        FINAL = 1, "FINAL"

    class Installments(models.IntegerChoices):
        ONE = 1, "ONE"
        TWO = 2, "TWO"
        THREE = 3, "THREE"
        FOUR = 4, "FOUR"
        FIVE = 5, "FIVE"
        SIX = 6, "SIX"
        SEVEN = 7, "SEVEN"
        EIGHT = 8, "EIGHT"

    status = models.PositiveSmallIntegerField(
        default=InvoiceStatus.DRAFT,
        choices=InvoiceStatus.choices,
        null=True,
        blank=True,
    )
    client_second_email = models.EmailField(null=True, blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    send_reminder = models.BooleanField(default=False, null=True, blank=True)

    late_penalty = models.BooleanField(default=False, null=True, blank=True)
    late_penalty_amount = models.DecimalField(
        default=0, max_digits=5, decimal_places=2, null=True, blank=True
    )

    discount_amount = models.DecimalField(
        default=0, max_digits=5, decimal_places=2, null=True, blank=True
    )
    tax_amount = models.DecimalField(
        default=0, max_digits=4, decimal_places=2, null=True, blank=True
    )
    installments = models.PositiveSmallIntegerField(
        default=Installments.ONE, choices=Installments.choices, blank=True
    )
    next_installment_date = models.DateTimeField(null=True, blank=True)

    def get_sent_invoice(self):
        if self.installments == 1:
            return self.invoice_snapshots.first()
        else:
            return self.invoice_snapshots.all()

    def get_installments_data(self):
        if self.installments == 1:
            return None
        return self.invoice_snapshots.count(), self.installments

    def invoice_type(self):
        return "single"

    def get_hours_stats(self):
        raise NotImplementedError()

    def is_synced(self):
        if self.installments == 1:
            sent_invoice = self.get_sent_invoice()
            if sent_invoice:
                if self.accounting_customer_id and sent_invoice.accounting_invoice_id:
                    return True
        elif self.installments > 1:
            return self.accounting_customer_id is not None
        return False

    def render_line_items(self, sent_invoice_id):
        ctx = {"line_items": self.line_items.all(), "single_invoice": self}
        if self.installments > 1:
            installments_left = self.installments - self.invoice_snapshots.count()
            # Add one installment to include this sent invoice in amount
            line_items = self.line_items.all().annotate(
                total_amount=(F("quantity") * F("unit_price")) / (installments_left + 1)
            )
            ctx["line_items"] = line_items
            sent_invoice = SentInvoice.objects.get(id=sent_invoice_id)
            if sent_invoice.is_payment_late():
                ctx["is_sent_invoice_late"] = True
        return render_to_string(
            "invoices/line_items/single.html",
            ctx,
        )

    def can_edit(self):
        if self.installments == 1:
            if not self.get_sent_invoice() or self.get_sent_invoice().paid_status == 0:
                return True
        if self.installments > 1:
            return (
                self.get_sent_invoice().filter(paid_status=2).count()
                != self.installments
            )

        return False

    def update(self):
        self.update_total_price()

    def update_next_installment_date(self):
        if self.invoice_snapshots.count() < self.installments:
            if self.next_installment_date is None:
                self.next_installment_date = timezone.now().astimezone(
                    tz=zoneinfo.ZoneInfo(self.user.timezone)
                )
            self.next_installment_date = (
                self.next_installment_date + timezone.timedelta(days=14)
            )
        else:
            self.next_installment_date = None
        self.save()

    def get_installment_price(self):
        total_amount_sent_so_far = (
            self.invoice_snapshots.aggregate(price=Sum("total_price"))["price"] or 0
        )
        balance_left = self.balance_due - total_amount_sent_so_far
        installments_left = self.installments - self.invoice_snapshots.count()
        return balance_left / installments_left

    def form_class(self, action="create"):
        from timary.forms import SingleInvoiceForm

        return SingleInvoiceForm

    def can_send_invoice(self):
        """
        Either the invoice has been sent if not started/failed
        or not sent at all
        or it can only be sent if the status is Final
        """
        if self.installments > 1:
            return False
        sent_invoice = self.get_sent_invoice()
        return (
            self.status == SingleInvoice.InvoiceStatus.FINAL
            and self.balance_due > 0
            and (
                (not sent_invoice)
                or (
                    sent_invoice.paid_status
                    in [
                        SentInvoice.PaidStatus.NOT_STARTED,
                        SentInvoice.PaidStatus.FAILED,
                        SentInvoice.PaidStatus.CANCELLED,
                    ]
                )
            )
        )

    def can_start_installments(self):
        return (
            self.status == SingleInvoice.InvoiceStatus.FINAL
            and self.balance_due > 0
            and self.installments > 1
            and self.invoice_snapshots.count() == 0
        )

    def update_total_price(self):
        total_price = 0.0
        for line_item in self.line_items.all():
            total_price += float(line_item.total_amount())

        if self.discount_amount:
            total_price -= float(self.discount_amount)

        if self.tax_amount:
            total_price += total_price * float(self.tax_amount / 100)

        if self.installments == 1:
            if self.is_payment_late():
                total_price += float(self.late_penalty_amount)

        self.balance_due = round(Decimal.from_float(total_price), 2)
        if self.installments == 1:
            if sent_invoice := self.get_sent_invoice():
                sent_invoice.total_price = self.balance_due
                sent_invoice.save()
        self.save()

    def is_payment_late(self):
        return self.late_penalty and self.due_date < timezone.now()


class RecurringInvoice(Invoice):
    next_date = models.DateTimeField(null=True, blank=True)
    last_date = models.DateTimeField(null=True, blank=True)

    def __repr__(self):
        return (
            f"RecurringInvoice(title={self.title}, "
            f"email_id={self.email_id}, "
            f"user={self.user}, "
            f"invoice_rate={self.rate}, "
            f"client_email={self.client_email}, "
            f"is_archived={self.is_archived})"
        )

    def get_hours_tracked(self):
        return (
            self.line_items.filter(
                date_tracked__gte=self.last_date.astimezone(
                    tz=zoneinfo.ZoneInfo(self.user.timezone)
                ),
                sent_invoice_id__isnull=True,
            )
            .exclude(quantity=0)
            .annotate(cost=self.rate * Sum("quantity"))
            .order_by("date_tracked")
        )

    def get_last_six_months(self):
        tz = zoneinfo.ZoneInfo(self.user.timezone)
        today = timezone.now().astimezone(tz=tz)
        date_times = [
            (today - relativedelta(months=m)).astimezone(tz=tz).date().replace(day=1)
            for m in range(0, 6)
        ]
        six_months_qs = (
            self.invoice_snapshots.exclude(paid_status=SentInvoice.PaidStatus.FAILED)
            .exclude(paid_status=SentInvoice.PaidStatus.CANCELLED)
            .annotate(month=TruncMonth("date_sent", output_field=DateField()))
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

    def get_hours_stats(self):
        hours_tracked = self.get_hours_tracked()
        total_hours = hours_tracked.aggregate(total_hours=Sum("quantity"))
        total_cost_amount = 0
        if total_hours["total_hours"]:
            total_cost_amount = total_hours["total_hours"] * self.rate
        return hours_tracked, total_cost_amount

    def budget_percentage(self):
        if not self.total_budget:
            return 0

        total_hours = self.line_items.filter(
            date_tracked__lte=timezone.now()
        ).aggregate(total_hours=Sum("quantity"))
        total_cost_amount = 0
        if total_hours["total_hours"]:
            total_cost_amount = total_hours["total_hours"] * self.rate

        return round((total_cost_amount / self.total_budget), ndigits=2) * 100

    def render_line_items(self, sent_invoice_id):
        return render_to_string(
            "invoices/line_items/hourly.html",
            {"line_items": self.get_hours_sent(sent_invoice_id).all()},
        )


class IntervalInvoice(RecurringInvoice):
    class Interval(models.TextChoices):
        WEEKLY = "W", "WEEKLY"
        BIWEEKLY = "B", "BIWEEKLY"
        MONTHLY = "M", "MONTHLY"
        QUARTERLY = "Q", "QUARTERLY"
        YEARLY = "Y", "YEARLY"

    invoice_interval = models.CharField(
        max_length=1,
        choices=Interval.choices,
        default=Interval.MONTHLY,
        blank=True,
        null=True,
    )

    def __repr__(self):
        return (
            f"IntervalInvoice(title={self.title}, "
            f"email_id={self.email_id}, "
            f"user={self.user}, "
            f"invoice_rate={self.rate}, "
            f"client_email={self.client_email}, "
            f"is_archived={self.is_archived})"
        )

    def invoice_type(self):
        return "interval"

    def update(self):
        self.calculate_next_date()

    def form_class(self, action="create"):
        from timary.forms import CreateIntervalForm, UpdateIntervalForm

        return CreateIntervalForm if action == "create" else UpdateIntervalForm

    def get_next_date(self):
        if self.invoice_interval == IntervalInvoice.Interval.WEEKLY:
            return timezone.timedelta(weeks=1)
        elif self.invoice_interval == IntervalInvoice.Interval.BIWEEKLY:
            return timezone.timedelta(weeks=2)
        elif self.invoice_interval == IntervalInvoice.Interval.MONTHLY:
            return timezone.timedelta(weeks=4)
        elif self.invoice_interval == IntervalInvoice.Interval.QUARTERLY:
            return timezone.timedelta(weeks=12)
        else:
            return timezone.timedelta(weeks=52)

    def calculate_next_date(self, update_last: bool = True):
        todays_date = get_users_localtime(self.user)
        self.next_date = todays_date + self.get_next_date()
        if update_last:
            self.last_date = todays_date
        self.save()


class WeeklyInvoice(RecurringInvoice):
    def __repr__(self):
        return (
            f"WeeklyInvoice(title={self.title}, "
            f"email_id={self.email_id}, "
            f"user={self.user}, "
            f"invoice_rate={self.rate}, "
            f"client_email={self.client_email}, "
            f"is_archived={self.is_archived})"
        )

    def invoice_type(self):
        return "weekly"

    def update(self):
        self.last_date = timezone.now()
        self.save()

    def form_class(self, action="create"):
        from timary.forms import CreateWeeklyForm, UpdateWeeklyForm

        return CreateWeeklyForm if action == "create" else UpdateWeeklyForm

    def budget_percentage(self):
        if not self.total_budget:
            return 0

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

    def get_hours_stats(self):
        return self.get_hours_tracked(), self.rate

    def render_line_items(self, sent_invoice_id):
        sent_invoice = get_object_or_404(SentInvoice, id=sent_invoice_id)
        return render_to_string(
            "invoices/line_items/weekly.html", {"sent_invoice": sent_invoice}
        )


class MilestoneInvoice(RecurringInvoice):
    milestone_total_steps = models.IntegerField(null=True, blank=True)
    milestone_step = models.IntegerField(default=0, null=True, blank=True)

    def __repr__(self):
        return (
            f"MilestoneInvoice(title={self.title}, "
            f"email_id={self.email_id}, "
            f"user={self.user}, "
            f"invoice_rate={self.rate}, "
            f"client_email={self.client_email}, "
            f"is_archived={self.is_archived})"
        )

    def invoice_type(self):
        return "milestone"

    def update(self):
        self.milestone_step += 1
        self.last_date = timezone.now()
        self.save()

    def form_class(self, action="create"):
        from timary.forms import CreateMilestoneForm, UpdateMilestoneForm

        return CreateMilestoneForm if action == "create" else UpdateMilestoneForm


class InvoiceManager:
    def __init__(self, invoice_id):
        try:
            invoice = IntervalInvoice.objects.get(id=invoice_id)
        except IntervalInvoice.DoesNotExist:
            try:
                invoice = WeeklyInvoice.objects.get(id=invoice_id)
            except WeeklyInvoice.DoesNotExist:
                try:
                    invoice = MilestoneInvoice.objects.get(id=invoice_id)
                except MilestoneInvoice.DoesNotExist:
                    try:
                        invoice = SingleInvoice.objects.get(id=invoice_id)
                    except SingleInvoice.DoesNotExist:
                        raise Http404("Invoice does not exist")
        self._invoice = invoice

    @staticmethod
    def fetch_by_email_id(email_id):
        try:
            invoice = IntervalInvoice.objects.get(email_id=email_id)
        except IntervalInvoice.DoesNotExist:
            try:
                invoice = WeeklyInvoice.objects.get(email_id=email_id)
            except WeeklyInvoice.DoesNotExist:
                try:
                    invoice = MilestoneInvoice.objects.get(email_id=email_id)
                except MilestoneInvoice.DoesNotExist:
                    raise Http404("Invoice does not exist")
        return invoice

    @property
    def invoice(self):
        return self._invoice

    @staticmethod
    def get_form(i_type, action="create"):
        invoice_form = None
        if i_type == "interval":
            from timary.forms import CreateIntervalForm, UpdateIntervalForm

            invoice_form = (
                CreateIntervalForm if action == "create" else UpdateIntervalForm
            )
        elif i_type == "milestone":
            from timary.forms import CreateMilestoneForm, UpdateMilestoneForm

            invoice_form = (
                CreateMilestoneForm if action == "create" else UpdateMilestoneForm
            )
        elif i_type == "weekly":
            from timary.forms import CreateWeeklyForm, UpdateWeeklyForm

            invoice_form = CreateWeeklyForm if action == "create" else UpdateWeeklyForm
        return invoice_form, f"invoices/{i_type}/_{action}.html"


class SentInvoice(BaseModel):
    class PaidStatus(models.IntegerChoices):
        NOT_STARTED = 0, "NOT STARTED"
        PENDING = 1, "PENDING"
        PAID = 2, "PAID"
        FAILED = 3, "FAILED"
        CANCELLED = 4, "CANCELLED"

    date_sent = models.DateTimeField(null=False, blank=False)
    due_date = models.DateTimeField(null=True, blank=True)
    invoice = models.ForeignKey(
        "timary.Invoice",
        on_delete=models.SET_NULL,
        related_name="invoice_snapshots",
        null=True,
        blank=True,
    )
    # Save the rate of the invoice when the invoice is sent for when editing is needed
    hourly_rate_snapshot = models.DecimalField(
        default=100,
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(1)],
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
            f"total_price={self.total_price}, "
            f"paid_status={self.get_paid_status_display()})"
        )

    def __repr__(self):
        return (
            f"SentInvoice(invoice={self.invoice}, "
            f"total_price={self.total_price}, "
            f"paid_status={self.get_paid_status_display()})"
        )

    @classmethod
    def create(cls, invoice):
        hours_tracked, total_cost = invoice.get_hours_stats()
        return SentInvoice.objects.create(
            date_sent=timezone.now(),
            invoice=invoice,
            user=invoice.user,
            total_price=total_cost,
            hourly_rate_snapshot=invoice.rate,
        )

    @property
    def email_id(self):
        return f"{str(self.id).split('-')[0]}"

    def get_hours_tracked(self):
        return self.invoice.get_hours_sent(sent_invoice_id=self.id)

    def get_rendered_line_items(self):
        return self.invoice.render_line_items(sent_invoice_id=self.id)

    def success_notification(self):
        """
        1) Sends a notification using Twilio to user, if phone number is found
        2) Sends email receipt to invoice recipient
        3) Pushes updates to available accounting services.
        """
        TwilioClient.sent_payment_success(self)

        msg_body = InvoiceBuilder(self.user).send_invoice_receipt(
            {
                "sent_invoice": self,
                "line_items": self.get_rendered_line_items(),
            }
        )
        EmailService.send_html(
            f"Here is a receipt for {self.invoice.user.first_name}'s services for {self.invoice.title}",
            msg_body,
            self.invoice.client_email,
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

        if self.accounting_invoice_id:
            return True, None

        try:
            AccountingService(
                {"user": self.user, "sent_invoice": self}
            ).create_invoice()
        except AccountingError as ae:
            error_reason = ae.log()
            return False, error_reason
        return True, None

    def update_total_price(self):
        hours = self.get_hours_tracked().all()
        total_price = Decimal(0.0)
        for hour in hours:
            total_price += hour.quantity * self.hourly_rate_snapshot
        self.total_price = total_price
        self.save()

    def update_installments(self):
        line_items = self.invoice.line_items.all()
        total_price = Decimal(0.0)
        for item in line_items:
            total_price += item.total_amount() / self.invoice.installments
        self.total_price = total_price
        if self.due_date and self.is_payment_late() and self.invoice.late_penalty:
            self.total_price += self.invoice.late_penalty_amount
        self.save()

    def is_payment_late(self):
        if self.invoice.installments == 1:
            return False
        if not self.invoice.late_penalty:
            return False
        tz = zoneinfo.ZoneInfo(self.user.timezone)
        now = timezone.now().astimezone(tz=tz)
        due_date = self.due_date.astimezone(tz=tz)
        return now > due_date


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
    stripe_subscription_recurring_price = models.IntegerField(blank=True, null=True)

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

    timezone = models.CharField(
        default="America/New_York", max_length=100, null=False, blank=False
    )

    # Accounting integration
    accounting_org = models.CharField(max_length=200, blank=True, null=True)
    accounting_org_id = models.CharField(max_length=200, null=True, blank=True)
    accounting_refresh_token = models.CharField(max_length=200, blank=True, null=True)

    profile_pic = models.ImageField(upload_to="profile_pics/", null=True, blank=True)

    # Custom invoice branding
    invoice_branding = models.JSONField(blank=True, null=True, default=dict)

    # Invite referral id
    referral_id = models.CharField(
        max_length=10, unique=True, default=create_new_ref_number
    )
    referrer_id = models.CharField(max_length=10, blank=True, null=True)

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
        today = get_users_localtime(self)
        today_range = (
            today.replace(hour=0, minute=0, second=0),
            today.replace(hour=23, minute=59, second=59),
        )
        invoices = self.get_invoices.exclude(is_paused=True).exclude(
            line_items__date_tracked__range=today_range
        )

        remaining_invoices = [inv for inv in invoices if inv.invoice_type() != "single"]
        return remaining_invoices if len(remaining_invoices) > 0 else None

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

    def add_referral_discount(self):
        if not self.settings["subscription_active"]:
            return
        subscription = StripeService.get_subscription(self.stripe_subscription_id)
        amount = 500  # $5
        if subscription["discount"]:
            # If a biz already has a discount applied to their account, max out the coupon to $10
            if subscription["discount"]["coupon"]["amount_off"] == amount:
                return StripeService.create_subscription_discount(
                    self, amount, subscription["id"]
                )

        else:
            return StripeService.create_subscription_discount(self, amount)

    def invoice_branding_properties(self):
        return {
            "due_date_selected": self.invoice_branding.get("due_date"),
            "next_weeks_date": date.today()
            + timedelta(weeks=int(self.invoice_branding.get("due_date") or 1)),
            "user_name": self.invoice_branding.get("company_name") or self.first_name,
            "hide_timary": self.invoice_branding.get("hide_timary") or False,
            "show_profile_pic": self.invoice_branding.get("show_profile_pic"),
            "profile_pic": self.profile_pic,
            "personal_website": self.invoice_branding.get("personal_website") or "",
            "linked_in": self.invoice_branding.get("linked_in") or "",
            "twitter": self.invoice_branding.get("twitter") or "",
            "youtube": self.invoice_branding.get("youtube") or "",
            "social_links": self.social_links_added(),
        }

    def social_links_added(self):
        links = ["personal_website", "linked_in", "twitter", "youtube"]
        any_links = any([self.invoice_branding.get(link) for link in links])
        return any_links

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
