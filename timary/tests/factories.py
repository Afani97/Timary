import zoneinfo

import factory
from django.utils import timezone
from factory.django import DjangoModelFactory
from factory.fuzzy import FuzzyDecimal

from timary.models import (
    Client,
    Expenses,
    HoursLineItem,
    IntervalInvoice,
    Invoice,
    LineItem,
    MilestoneInvoice,
    SentInvoice,
    SingleInvoice,
    User,
    WeeklyInvoice,
    Proposal,
)

username_email = factory.Faker("email")


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Faker("email")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    email = factory.LazyAttribute(lambda o: f"{o.username}")
    password = factory.PostGenerationMethodCall("set_password", "Apple101!")
    phone_number = factory.Faker("phone_number", locale="en_US")
    phone_number_availability = factory.Iterator(
        ["Mon", "Tue", "Wed", "Thur", "Fri", "Sat", "Sun"]
    )
    phone_number_repeat_sms = False
    stripe_subscription_status = 2


def get_localtime():
    return timezone.now().astimezone(tz=zoneinfo.ZoneInfo("America/New_York"))


def get_next_date():
    return (timezone.now() + timezone.timedelta(weeks=2)).astimezone(
        tz=zoneinfo.ZoneInfo("America/New_York")
    )


def get_last_date():
    return timezone.now() - timezone.timedelta(weeks=1)


class ClientFactory(DjangoModelFactory):
    class Meta:
        model = Client

    email = factory.Faker("email")
    name = factory.Faker("name")
    user = factory.SubFactory(UserFactory)


class InvoiceFactory(DjangoModelFactory):
    class Meta:
        model = Invoice

    user = factory.SubFactory(UserFactory)
    client = factory.SubFactory(ClientFactory)
    title = factory.Faker("first_name")
    total_budget = factory.Faker("pyint", min_value=1000, max_value=10_000)
    rate = factory.Faker("pyint", min_value=100, max_value=1000)
    balance_due = factory.Faker("pyint", min_value=1000, max_value=1000)
    is_archived = False
    is_paused = False


class WeeklyInvoiceFactory(InvoiceFactory):
    class Meta:
        model = WeeklyInvoice

    next_date = factory.LazyFunction(get_next_date)
    last_date = factory.LazyFunction(get_last_date)
    rate = factory.Faker("pyint", min_value=1000, max_value=1000)
    sms_ping_today = False


class IntervalInvoiceFactory(WeeklyInvoiceFactory):
    class Meta:
        model = IntervalInvoice

    invoice_interval = factory.Iterator(
        [
            IntervalInvoice.Interval.WEEKLY,
            IntervalInvoice.Interval.BIWEEKLY,
            IntervalInvoice.Interval.MONTHLY,
            IntervalInvoice.Interval.QUARTERLY,
            IntervalInvoice.Interval.YEARLY,
        ]
    )


class MilestoneInvoiceFactory(WeeklyInvoiceFactory):
    class Meta:
        model = MilestoneInvoice

    milestone_total_steps = factory.Faker("pyint", min_value=2, max_value=10)
    milestone_step = factory.Faker("pyint", min_value=3, max_value=9)


class SingleInvoiceFactory(InvoiceFactory):
    class Meta:
        model = SingleInvoice

    status = factory.Iterator(
        [
            SingleInvoice.InvoiceStatus.DRAFT,
            SingleInvoice.InvoiceStatus.FINAL,
        ]
    )
    due_date = factory.LazyFunction(get_next_date)


class SentInvoiceFactory(DjangoModelFactory):
    class Meta:
        model = SentInvoice

    user = factory.SubFactory(UserFactory)
    invoice = factory.SubFactory(IntervalInvoiceFactory)
    date_sent = factory.LazyFunction(timezone.now)
    total_price = FuzzyDecimal(100, 10_000)
    paid_status = SentInvoice.PaidStatus.NOT_STARTED


class HoursLineItemFactory(DjangoModelFactory):
    class Meta:
        model = HoursLineItem

    invoice = factory.SubFactory(IntervalInvoiceFactory)
    quantity = FuzzyDecimal(1, 10, 1)
    date_tracked = factory.LazyFunction(get_localtime)


class LineItemFactory(DjangoModelFactory):
    class Meta:
        model = LineItem

    invoice = factory.SubFactory(IntervalInvoiceFactory)
    description = factory.Faker("name")
    unit_price = FuzzyDecimal(1, 10, 1)
    quantity = FuzzyDecimal(1, 10, 1)
    date_tracked = factory.LazyFunction(get_localtime)


class ExpenseFactory(DjangoModelFactory):
    class Meta:
        model = Expenses

    invoice = factory.SubFactory(IntervalInvoiceFactory)
    description = factory.Faker("name")
    cost = FuzzyDecimal(1, 10, 1)
    date_tracked = factory.LazyFunction(get_localtime)


class ProposalFactory(DjangoModelFactory):
    class Meta:
        model = Proposal

    client = factory.SubFactory(ClientFactory)
    title = factory.Faker("name")
    body = factory.Faker("text")
    user_signature = factory.Faker("name")
    date_send = factory.LazyFunction(get_localtime)
    date_user_signed = factory.LazyFunction(get_localtime)
