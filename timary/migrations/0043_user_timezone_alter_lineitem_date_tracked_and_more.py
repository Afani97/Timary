# Generated by Django 4.1.4 on 2023-01-20 22:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("timary", "0042_alter_sentinvoice_paid_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="timezone",
            field=models.CharField(default="America/New_York", max_length=100),
        ),
        migrations.AlterField(
            model_name="lineitem",
            name="date_tracked",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="recurringinvoice",
            name="last_date",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="recurringinvoice",
            name="next_date",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="sentinvoice",
            name="date_sent",
            field=models.DateTimeField(),
        ),
        migrations.AlterField(
            model_name="singleinvoice",
            name="due_date",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
