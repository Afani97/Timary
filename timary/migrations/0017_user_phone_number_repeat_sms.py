# Generated by Django 4.1.4 on 2022-12-23 05:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("timary", "0016_user_stripe_subscription_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="phone_number_repeat_sms",
            field=models.BooleanField(default=False),
        ),
    ]