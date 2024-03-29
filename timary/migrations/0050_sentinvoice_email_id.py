# Generated by Django 4.1.6 on 2023-03-11 16:14
import random

from django.db import migrations, models

import timary.models


def create_new_ref_number():
    return str(random.randint(1000000000, 9999999999))


def assign_unique_email_id_to_sent_invoices(apps, schema_editor):
    SentInvoice = apps.get_model("timary", "SentInvoice")
    for sent_invoice in SentInvoice.objects.all():
        sent_invoice.email_id = create_new_ref_number()
        sent_invoice.save()


class Migration(migrations.Migration):
    dependencies = [
        ("timary", "0049_client_address_client_phone_number"),
    ]

    operations = [
        migrations.AddField(
            model_name="sentinvoice",
            name="email_id",
            field=models.CharField(
                default=timary.models.create_new_ref_number, max_length=10
            ),
        ),
        migrations.RunPython(
            code=assign_unique_email_id_to_sent_invoices,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="sentinvoice",
            name="email_id",
            field=models.CharField(
                default=timary.models.create_new_ref_number, max_length=10, unique=True
            ),
        ),
    ]
