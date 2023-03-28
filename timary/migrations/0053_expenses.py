# Generated by Django 4.1.6 on 2023-03-28 02:10

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("timary", "0052_invoice_feedback"),
    ]

    operations = [
        migrations.CreateModel(
            name="Expenses",
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
                ("date_tracked", models.DateTimeField(blank=True, null=True)),
                ("description", models.CharField(max_length=500)),
                (
                    "cost",
                    models.DecimalField(decimal_places=2, default=0, max_digits=9),
                ),
                (
                    "invoice",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="expenses",
                        to="timary.invoice",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
    ]
