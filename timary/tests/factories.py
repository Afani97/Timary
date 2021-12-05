import datetime

import factory
from factory.django import DjangoModelFactory
from factory.fuzzy import FuzzyInteger

from timary import models
from timary.models import Invoice, User

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


def get_next_date():
    return datetime.date.today() + datetime.timedelta(weeks=2)


def get_last_date():
    return datetime.date.today() - datetime.timedelta(weeks=1)


class InvoiceFactory(DjangoModelFactory):
    class Meta:
        model = models.Invoice

    user = factory.SubFactory(UserFactory)
    title = factory.Faker("name")
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
    email_recipient = factory.Faker("email")
    email_recipient_name = factory.Faker("name")
    next_date = factory.LazyFunction(datetime.date.today)
    last_date = factory.LazyFunction(get_last_date)


class DailyHoursFactory(DjangoModelFactory):
    class Meta:
        model = models.DailyHoursInput

    invoice = factory.SubFactory(InvoiceFactory)
    hours = FuzzyInteger(1, 23)
    date_tracked = factory.LazyFunction(datetime.date.today)
