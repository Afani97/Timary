import datetime

from django.core.management.base import BaseCommand

from timary.tasks import send_invoice
from timary.tests.factories import DailyHoursFactory, InvoiceFactory, UserFactory


class Command(BaseCommand):
    help = "Generate fake invoicing email"

    def add_arguments(self, parser):
        # Membership type
        # FREE => 1, BASIC => 2, PREMIUM => 3
        parser.add_argument("-mt", nargs="?", type=int, default=1)

    def handle(self, *args, **options):
        membership_tier = options["mt"]
        user = UserFactory(
            email="aristotelf@gmail.com",
            membership_tier=membership_tier,
            stripe_payouts_enabled=True,
            phone_number=None,
            quickbooks_realm_id="4620816365214495060",
        )
        invoice = InvoiceFactory(
            user=user,
            email_recipient="aristotelf@gmail.com",
            last_date=datetime.date.today() - datetime.timedelta(days=3),
            quickbooks_customer_ref_id="58",
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

        send_invoice(invoice.id)
