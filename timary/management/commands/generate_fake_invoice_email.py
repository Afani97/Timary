from django.core.management.base import BaseCommand

from timary.tasks import send_invoice
from timary.tests.factories import DailyHoursFactory, InvoiceFactory, UserFactory


class Command(BaseCommand):
    help = "Generate fake invoicing email"

    def handle(self, *args, **options):
        user = UserFactory(email="aristotelf@gmail.com")
        invoice = InvoiceFactory(user=user, email_recipient="aristotelf@gmail.com")
        DailyHoursFactory(invoice=invoice)

        send_invoice(invoice.id)
