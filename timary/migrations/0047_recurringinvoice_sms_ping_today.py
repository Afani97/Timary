# Generated by Django 4.1.6 on 2023-02-23 00:52

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("timary", "0046_remove_invoice_accounting_customer_id_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="recurringinvoice",
            name="sms_ping_today",
            field=models.BooleanField(blank=True, default=False, null=True),
        ),
    ]
