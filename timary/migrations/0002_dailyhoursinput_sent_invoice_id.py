# Generated by Django 3.2.13 on 2022-04-25 23:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("timary", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="dailyhoursinput",
            name="sent_invoice_id",
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
    ]