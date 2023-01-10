import datetime

from django.core.management.base import BaseCommand

from timary.tasks import send_invoice_preview
from timary.tests.factories import DailyHoursFactory, InvoiceFactory, UserFactory


class Command(BaseCommand):
    help = "Generate fake invoicing preview email"

    def handle(self, *args, **options):
        user = UserFactory(
            email="aristotelf@gmail.com",
            stripe_payouts_enabled=True,
            phone_number=None,
        )
        invoice = InvoiceFactory(
            user=user,
            client_email="aristotelf@gmail.com",
            last_date=datetime.date.today() - datetime.timedelta(days=3),
            accounting_customer_id="58",
        )
        DailyHoursFactory(invoice=invoice)
        DailyHoursFactory(
            invoice=invoice,
            date_tracked=datetime.date.today() - datetime.timedelta(days=1),
        )
        DailyHoursFactory(
            invoice=invoice,
            date_tracked=datetime.date.today() - datetime.timedelta(days=2),
        )

        send_invoice_preview(invoice.id)
