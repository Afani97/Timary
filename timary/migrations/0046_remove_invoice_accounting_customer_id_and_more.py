# Generated by Django 4.1.6 on 2023-02-21 02:17

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("timary", "0045_sentinvoice_due_date_singleinvoice_installments_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="invoice",
            name="accounting_customer_id",
        ),
        migrations.RemoveField(
            model_name="invoice",
            name="client_email",
        ),
        migrations.RemoveField(
            model_name="invoice",
            name="client_name",
        ),
        migrations.RemoveField(
            model_name="invoice",
            name="client_stripe_customer_id",
        ),
        migrations.RemoveField(
            model_name="singleinvoice",
            name="client_second_email",
        ),
        migrations.CreateModel(
            name="Client",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        db_index=True,
                        default=uuid.uuid4,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=200)),
                ("email", models.EmailField(max_length=254)),
                (
                    "second_email",
                    models.EmailField(blank=True, max_length=254, null=True),
                ),
                (
                    "stripe_customer_id",
                    models.CharField(blank=True, max_length=200, null=True),
                ),
                (
                    "accounting_customer_id",
                    models.CharField(blank=True, max_length=200, null=True),
                ),
                (
                    "user",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="my_clients",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.AddField(
            model_name="invoice",
            name="client",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="clients",
                to="timary.client",
            ),
        ),
    ]
