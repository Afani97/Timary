# Generated by Django 3.2.8 on 2021-10-31 19:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("timary", "0002_invoice_email_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="email_recipient_name",
            field=models.CharField(default="", max_length=200),
            preserve_default=False,
        ),
    ]
