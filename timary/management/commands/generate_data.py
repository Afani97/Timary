import datetime
import random

from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand

from timary.models import SentInvoice, User
from timary.tests.factories import DailyHoursFactory, InvoiceFactory, SentInvoiceFactory


class Command(BaseCommand):
    help = "Generate fake data"

    def handle(self, *args, **options):
        user = User.objects.get(username="aristotelf@gmail.com")
        for i in range(0, 3):
            invoice = InvoiceFactory(
                user=user,
                email_recipient="aristotelf@gmail.com",
                last_date=datetime.date.today() - datetime.timedelta(days=3),
            )
            for _ in range(0, 50):
                random_int = random.randint(0, 3)
                DailyHoursFactory(
                    invoice=invoice,
                    date_tracked=datetime.date.today() - relativedelta(months=i),
                )
            for _ in range(0, 5):
                random_int = random.randint(0, 3)
                SentInvoiceFactory(
                    invoice=invoice,
                    user=user,
                    total_price=float(random.randint(100, 500)),
                    date_sent=datetime.date.today() - relativedelta(months=random_int),
                )

            for _ in range(0, 5):
                random_int = random.randint(2, 12)
                SentInvoiceFactory(
                    invoice=invoice,
                    user=user,
                    total_price=float(random.randint(100, 500)),
                    date_sent=datetime.date.today() - relativedelta(weeks=random_int),
                    paid_status=SentInvoice.PaidStatus.PAID,
                )
