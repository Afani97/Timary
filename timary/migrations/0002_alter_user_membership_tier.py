# Generated by Django 3.2.10 on 2022-03-18 14:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("timary", "0001_squashed_0020_invoice_total_budget"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="membership_tier",
            field=models.PositiveSmallIntegerField(
                choices=[
                    (5, "STARTER"),
                    (19, "PROFESSIONAL"),
                    (49, "BUSINESS"),
                    (1, "INVOICE_FEE"),
                ],
                default=5,
            ),
        ),
    ]
