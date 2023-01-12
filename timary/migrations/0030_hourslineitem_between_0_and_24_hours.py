# Generated by Django 4.1.4 on 2023-01-12 01:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("timary", "0029_remove_hourslineitem_hours_and_more"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="hourslineitem",
            constraint=models.CheckConstraint(
                check=models.Q(("quantity__gte", 0), ("quantity__lt", 24)),
                name="between_0_and_24_hours",
            ),
        ),
    ]
