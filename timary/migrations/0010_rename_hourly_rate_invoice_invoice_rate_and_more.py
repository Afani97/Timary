# Generated by Django 4.0.7 on 2022-08-23 22:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("timary", "0009_auto_20220818_2147"),
    ]

    operations = [
        migrations.RenameField(
            model_name="invoice",
            old_name="invoice_rate",
            new_name="invoice_rate",
        ),
        migrations.AlterField(
            model_name="invoice",
            name="invoice_type",
            field=models.IntegerField(
                choices=[(1, "INTERVAL"), (2, "MILESTONE"), (3, "WEEKLY")], default=1
            ),
        ),
    ]
