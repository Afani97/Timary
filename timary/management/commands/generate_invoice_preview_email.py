import datetime

from django.core.management.base import BaseCommand

from timary.models import User
from timary.tasks import send_invoice_preview
from timary.tests.factories import DailyHoursFactory, InvoiceFactory, UserFactory


class Command(BaseCommand):
    help = "Generate fake invoicing preview email"

    def add_arguments(self, parser):
        # Membership type
        # FREE => 1, BASIC => 2, PREMIUM => 3, INVOICE_FEE => 4
        parser.add_argument("-mt", nargs="?", type=str, default="1")

    def handle(self, *args, **options):
        membership_tiers = {
            "1": User.MembershipTier.STARTER,
            "2": User.MembershipTier.PROFESSIONAL,
            "3": User.MembershipTier.BUSINESS,
            "4": User.MembershipTier.INVOICE_FEE,
        }
        user = UserFactory(
            email="aristotelf@gmail.com",
            membership_tier=membership_tiers[options["mt"]],
            stripe_payouts_enabled=True,
            phone_number=None,
        )
        invoice = InvoiceFactory(
            user=user,
            email_recipient="aristotelf@gmail.com",
            last_date=datetime.date.today() - datetime.timedelta(days=3),
            quickbooks_customer_ref_id="58",
            freshbooks_client_id="204228",
            zoho_contact_id="3159267000000079014",
            xero_contact_id="c0edb30d-dacf-4f3a-8362-a8c1a8327ba6",
            sage_contact_id="f2ebbcbc57b043719da8000179a75d6c",
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