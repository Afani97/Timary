# Generated by Django 4.1.8 on 2023-04-16 04:13

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("timary", "0053_expenses"),
    ]

    operations = [
        migrations.CreateModel(
            name="Proposal",
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
                ("title", models.CharField(max_length=200)),
                ("date_send", models.DateTimeField(blank=True, null=True)),
                ("user_signature", models.CharField(max_length=200)),
                ("date_user_signed", models.DateTimeField()),
                ("client_signature", models.TextField(blank=True, null=True)),
                ("date_client_signed", models.DateTimeField(blank=True, null=True)),
                ("body", models.TextField()),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="proposals",
                        to="timary.client",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
    ]