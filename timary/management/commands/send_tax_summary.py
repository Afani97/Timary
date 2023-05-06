from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.management import call_command
from django.core.management.base import BaseCommand

from timary.models import User
from timary.tax_summary import TaxSummary


class Command(BaseCommand):
    help = "Send tax summaries in pdf for year"

    def add_arguments(self, parser):
        parser.add_argument("tax_year", type=int)

    # To send all the summaries at once: python manage.py send_tax_summary TAX_YEAR
    def handle(self, *args, **options):
        tax_year = int(options["tax_year"])
        income_year = tax_year - 1
        self.stdout.write(f"Sending tax summaries for {tax_year}")

        call_command("waffle_switch", f"can_view_{tax_year}", "on", "--create")

        for user in User.objects.all():
            html, stylesheet = TaxSummary(user, tax_year).generate_html(
                skip_if_none=True
            )
            if not html:
                continue

            self.stdout.write(f"Sending tax summaries for {user.first_name}")

            msg = EmailMultiAlternatives(
                f"Your {income_year} profit and loss summary is available to view.",
                "",
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
            )
            msg.attach(
                f"{income_year}_profit_loss_summary.pdf",
                html.write_pdf(stylesheets=[stylesheet]),
                "application/pdf",
            )
            msg.send(fail_silently=False)
        self.stdout.write(f"Finished sending tax summaries for {tax_year}")
