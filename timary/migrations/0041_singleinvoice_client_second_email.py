# Generated by Django 4.1.4 on 2023-01-15 21:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("timary", "0001_squashed_0040_alter_singleinvoice_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="singleinvoice",
            name="client_second_email",
            field=models.EmailField(blank=True, max_length=254, null=True),
        ),
    ]
