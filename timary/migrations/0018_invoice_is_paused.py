# Generated by Django 4.1.4 on 2022-12-24 05:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("timary", "0017_user_phone_number_repeat_sms"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="is_paused",
            field=models.BooleanField(blank=True, default=False, null=True),
        ),
    ]