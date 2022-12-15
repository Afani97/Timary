# Generated by Django 4.1.2 on 2022-12-08 02:32

from django.db import migrations, models
from django.db.models import Sum


def update_total_prices_to_decimals(apps, schema_editor):
    SentInvoice = apps.get_model("timary", "SentInvoice")
    for sent_invoice in SentInvoice.objects.all():
        hours_tracked = (
            sent_invoice.invoice.hours_tracked.filter(sent_invoice_id=sent_invoice.id)
            .exclude(hours=0)
            .order_by("date_tracked")
        )
        total_cost_amount = sent_invoice.total_price
        if sent_invoice.invoice.invoice_type != 3:  # Weekly
            total_hours = hours_tracked.aggregate(total_hours=Sum("hours"))
            if total_hours["total_hours"]:
                total_cost_amount = (
                    total_hours["total_hours"] * sent_invoice.invoice.invoice_rate
                )
        sent_invoice.total_price = total_cost_amount
        sent_invoice.save()


class Migration(migrations.Migration):

    dependencies = [
        ("timary", "0014_alter_sentinvoice_paid_status"),
    ]

    operations = [
        migrations.AlterField(
            model_name="sentinvoice",
            name="total_price",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=9),
        ),
        migrations.RunPython(
            update_total_prices_to_decimals, reverse_code=migrations.RunPython.noop
        ),
    ]