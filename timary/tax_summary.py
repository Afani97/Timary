import datetime
import zoneinfo

from django.db.models import Sum
from django.template.loader import render_to_string
from weasyprint import CSS, HTML

from timary.models import SentInvoice


class TaxSummary:
    def __init__(self, user, tax_year):
        self.user = user
        self.tax_year = tax_year
        self.income_year = self.tax_year - 1
        tz_info = zoneinfo.ZoneInfo(user.timezone)
        self.year_date_range = (
            datetime.datetime(year=self.income_year, month=1, day=1, tzinfo=tz_info),
            datetime.datetime(year=self.tax_year, month=1, day=1, tzinfo=tz_info),
        )

    def _calculate_profit_and_loss(self, invoices):
        summary_invoices = []
        total_gross_profit = 0
        total_expenses_paid = 0
        for invoice in invoices:
            inv = {"invoice": invoice}

            sent_invoices = invoice.invoice_snapshots.filter(
                paid_status=SentInvoice.PaidStatus.PAID
            ).filter(date_paid__range=self.year_date_range)

            inv["sent_invoices"] = sent_invoices
            inv["profit"] = (
                sent_invoices.aggregate(total=Sum("total_price"))["total"] or 0
            )
            total_gross_profit += inv["profit"]

            expenses = invoice.expenses.filter(date_tracked__range=self.year_date_range)
            inv["expenses"] = expenses
            inv["expenses_paid"] = expenses.aggregate(total=Sum("cost"))["total"] or 0
            total_expenses_paid += inv["expenses_paid"]

            if inv["profit"] > 0 or inv["expenses_paid"] > 0:
                summary_invoices.append(inv)

        return total_gross_profit, total_expenses_paid, summary_invoices

    def generate_html(self, skip_if_none=False):
        invoices = self.user.get_all_invoices()

        (
            total_gross_profit,
            total_expenses_paid,
            summary_invoices,
        ) = self._calculate_profit_and_loss(invoices)

        if skip_if_none and len(summary_invoices) == 0:
            return None, None

        html = HTML(
            string=render_to_string(
                "taxes/profit_loss_summary/summary.html",
                {
                    "year": self.income_year,
                    "invoices_summary": summary_invoices,
                    "total_gross_profit": total_gross_profit,
                    "total_expenses_paid": total_expenses_paid,
                },
            )
        )
        stylesheet = CSS(
            string=render_to_string("taxes/profit_loss_summary/summary.css", {})
        )
        return html, stylesheet
