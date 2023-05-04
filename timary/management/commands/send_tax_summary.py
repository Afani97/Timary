import datetime
import zoneinfo

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db.models import Sum
from django.template.loader import render_to_string
from weasyprint import CSS, HTML

from timary.models import SentInvoice, User


class Command(BaseCommand):
    help = "Send tax summaries in pdf for year"

    def add_arguments(self, parser):
        parser.add_argument("tax_year", type=int)

    # To send all the summaries at once: python manage.py send_tax_summary TAX_YEAR
    def handle(self, *args, **options):
        tax_year = int(options["tax_year"])
        income_year = tax_year - 1
        self.stdout.write(f"Send tax summaries for {tax_year} year")

        call_command("waffle_switch", f"can_view_{tax_year}", "on", "--create")

        for user in User.objects.all():
            tz_info = zoneinfo.ZoneInfo(user.timezone)
            year_date_range = (
                datetime.datetime(year=income_year, month=1, day=1, tzinfo=tz_info),
                datetime.datetime(year=tax_year, month=1, day=1, tzinfo=tz_info),
            )

            invoices = user.get_all_invoices()

            summary_invoices = []

            total_gross_profit = 0
            total_expenses_paid = 0
            for invoice in invoices:
                inv = {"invoice": invoice}
                sent_invoices = invoice.invoice_snapshots.filter(
                    paid_status=SentInvoice.PaidStatus.PAID
                ).filter(date_paid__range=year_date_range)

                inv["sent_invoices"] = sent_invoices
                inv["profit"] = (
                    sent_invoices.aggregate(total=Sum("total_price"))["total"] or 0
                )
                total_gross_profit += inv["profit"]

                expenses = invoice.expenses.filter(date_tracked__range=year_date_range)
                inv["expenses"] = expenses
                inv["expenses_paid"] = (
                    expenses.aggregate(total=Sum("cost"))["total"] or 0
                )
                total_expenses_paid += inv["expenses_paid"]
                if inv["profit"] > 0 or inv["expenses_paid"] > 0:
                    summary_invoices.append(inv)

            if len(summary_invoices) == 0:
                continue

            html = HTML(
                string=render_to_string(
                    "taxes/profit_loss_summary/summary.html",
                    {
                        "year": income_year,
                        "invoices_summary": summary_invoices,
                        "total_gross_profit": total_gross_profit,
                        "total_expenses_paid": total_expenses_paid,
                    },
                )
            )
            stylesheet = CSS(
                string=render_to_string("taxes/profit_loss_summary/summary.css", {})
            )

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
