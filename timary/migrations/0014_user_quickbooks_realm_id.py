# Generated by Django 3.2.10 on 2022-02-05 19:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("timary", "0013_auto_20220129_1822"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="quickbooks_realm_id",
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
    ]
