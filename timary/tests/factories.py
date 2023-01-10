import datetime

import factory
from factory.django import DjangoModelFactory
from factory.fuzzy import FuzzyDecimal

from timary.models import DailyHoursInput, Invoice, SentInvoice, User

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


def get_next_date():
    return datetime.date.today() + datetime.timedelta(weeks=2)


def get_last_date():
    return datetime.date.today() - datetime.timedelta(weeks=1)


class InvoiceFactory(DjangoModelFactory):
    class Meta:
        model = Invoice

    user = factory.SubFactory(UserFactory)
    title = factory.Faker("first_name")
    invoice_type = Invoice.InvoiceType.INTERVAL
    invoice_interval = factory.Iterator(
        [
            Invoice.Interval.DAILY,
            Invoice.Interval.WEEKLY,
            Invoice.Interval.BIWEEKLY,
            Invoice.Interval.MONTHLY,
            Invoice.Interval.QUARTERLY,
            Invoice.Interval.YEARLY,
        ]
    )
    milestone_total_steps = factory.Faker("pyint", min_value=2, max_value=10)
    milestone_step = factory.Faker("pyint", min_value=3, max_value=9)
    client_email = factory.Faker("email")
    client_name = factory.Faker("name")
    next_date = factory.LazyFunction(datetime.date.today)
    last_date = factory.LazyFunction(get_last_date)
    total_budget = factory.Faker("pyint", min_value=1000, max_value=10_000)
    is_archived = False
    is_paused = False


class SentInvoiceFactory(DjangoModelFactory):
    class Meta:
        model = SentInvoice

    user = factory.SubFactory(UserFactory)
    invoice = factory.SubFactory(InvoiceFactory)
    hours_start_date = factory.LazyFunction(get_last_date)
    hours_end_date = factory.LazyFunction(datetime.date.today)
    date_sent = factory.LazyFunction(datetime.date.today)
    total_price = FuzzyDecimal(100, 10_000)
    paid_status = SentInvoice.PaidStatus.NOT_STARTED


class DailyHoursFactory(DjangoModelFactory):
    class Meta:
        model = DailyHoursInput

    invoice = factory.SubFactory(InvoiceFactory)
    hours = FuzzyDecimal(1, 23, 1)
    date_tracked = factory.LazyFunction(datetime.date.today)
