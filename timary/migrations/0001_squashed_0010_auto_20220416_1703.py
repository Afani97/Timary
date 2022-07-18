# Generated by Django 3.2.13 on 2022-07-18 03:18

import uuid

import django.contrib.auth.models
import django.contrib.auth.validators
import django.core.validators
import django.db.migrations.operations.special
import django.db.models.deletion
import django.utils.timezone
import multiselectfield.db.fields
import phonenumber_field.modelfields
from django.conf import settings
from django.db import migrations, models

import timary.models


class Migration(migrations.Migration):

    replaces = [
        ("timary", "0001_squashed_0020_invoice_total_budget"),
        ("timary", "0002_alter_user_membership_tier"),
        ("timary", "0003_alter_user_membership_tier"),
        ("timary", "0004_auto_20220319_2137"),
        ("timary", "0005_auto_20220319_2015"),
        ("timary", "0006_auto_20220322_1910"),
        ("timary", "0007_auto_20220328_1948"),
        ("timary", "0008_alter_sentinvoice_invoice"),
        ("timary", "0009_invoice_email_recipient_stripe_customer_id"),
        ("timary", "0010_auto_20220416_1703"),
    ]

    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="User",
            fields=[
                ("password", models.CharField(max_length=128, verbose_name="password")),
                (
                    "last_login",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="last login"
                    ),
                ),
                (
                    "is_superuser",
                    models.BooleanField(
                        default=False,
                        help_text="Designates that this user has all permissions without explicitly assigning them.",
                        verbose_name="superuser status",
                    ),
                ),
                (
                    "username",
                    models.CharField(
                        error_messages={
                            "unique": "A user with that username already exists."
                        },
                        help_text="Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.",
                        max_length=150,
                        unique=True,
                        validators=[
                            django.contrib.auth.validators.UnicodeUsernameValidator()
                        ],
                        verbose_name="username",
                    ),
                ),
                (
                    "first_name",
                    models.CharField(
                        blank=True, max_length=150, verbose_name="first name"
                    ),
                ),
                (
                    "last_name",
                    models.CharField(
                        blank=True, max_length=150, verbose_name="last name"
                    ),
                ),
                (
                    "email",
                    models.EmailField(
                        blank=True, max_length=254, verbose_name="email address"
                    ),
                ),
                (
                    "is_staff",
                    models.BooleanField(
                        default=False,
                        help_text="Designates whether the user can log into this admin site.",
                        verbose_name="staff status",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Designates whether this user should be treated as active. Unselect this instead of deleting accounts.",
                        verbose_name="active",
                    ),
                ),
                (
                    "date_joined",
                    models.DateTimeField(
                        default=django.utils.timezone.now, verbose_name="date joined"
                    ),
                ),
                (
                    "id",
                    models.UUIDField(
                        db_index=True,
                        default=uuid.uuid4,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "phone_number",
                    phonenumber_field.modelfields.PhoneNumberField(
                        blank=True, max_length=128, null=True, region=None, unique=True
                    ),
                ),
                (
                    "groups",
                    models.ManyToManyField(
                        blank=True,
                        help_text="The groups this user belongs to. A user will get all permissions granted to each of their groups.",
                        related_name="user_set",
                        related_query_name="user",
                        to="auth.Group",
                        verbose_name="groups",
                    ),
                ),
                (
                    "user_permissions",
                    models.ManyToManyField(
                        blank=True,
                        help_text="Specific permissions for this user.",
                        related_name="user_set",
                        related_query_name="user",
                        to="auth.Permission",
                        verbose_name="user permissions",
                    ),
                ),
                (
                    "membership_tier",
                    models.PositiveSmallIntegerField(
                        blank=True,
                        choices=[
                            (5, "STARTER"),
                            (19, "PROFESSIONAL"),
                            (49, "BUSINESS"),
                            (1, "INVOICE_FEE"),
                        ],
                        default=5,
                    ),
                ),
                (
                    "stripe_customer_id",
                    models.CharField(blank=True, max_length=200, null=True),
                ),
                (
                    "stripe_connect_id",
                    models.CharField(blank=True, max_length=200, null=True),
                ),
                (
                    "stripe_subscription_id",
                    models.CharField(blank=True, max_length=200, null=True),
                ),
                ("stripe_payouts_enabled", models.BooleanField(default=False)),
                (
                    "phone_number_availability",
                    multiselectfield.db.fields.MultiSelectField(
                        blank=True,
                        choices=[
                            ("Mon", "Mon"),
                            ("Tue", "Tue"),
                            ("Wed", "Wed"),
                            ("Thu", "Thu"),
                            ("Fri", "Fri"),
                            ("Sat", "Sat"),
                            ("Sun", "Sun"),
                        ],
                        max_length=27,
                        null=True,
                    ),
                ),
                (
                    "quickbooks_realm_id",
                    models.CharField(blank=True, max_length=200, null=True),
                ),
                (
                    "freshbooks_account_id",
                    models.CharField(blank=True, max_length=200, null=True),
                ),
                (
                    "xero_tenant_id",
                    models.CharField(blank=True, max_length=200, null=True),
                ),
                (
                    "zoho_organization_id",
                    models.CharField(blank=True, max_length=200, null=True),
                ),
                (
                    "freshbooks_refresh_token",
                    models.CharField(blank=True, max_length=200, null=True),
                ),
                (
                    "quickbooks_refresh_token",
                    models.CharField(blank=True, max_length=200, null=True),
                ),
                (
                    "xero_refresh_token",
                    models.CharField(blank=True, max_length=200, null=True),
                ),
                (
                    "zoho_refresh_token",
                    models.CharField(blank=True, max_length=200, null=True),
                ),
                (
                    "sage_account_id",
                    models.CharField(blank=True, max_length=200, null=True),
                ),
                (
                    "sage_refresh_token",
                    models.CharField(blank=True, max_length=200, null=True),
                ),
            ],
            options={
                "verbose_name": "user",
                "verbose_name_plural": "users",
                "abstract": False,
            },
            managers=[
                ("objects", django.contrib.auth.models.UserManager()),
            ],
        ),
        migrations.CreateModel(
            name="Invoice",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        db_index=True,
                        default=uuid.uuid4,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "email_id",
                    models.CharField(
                        default=timary.models.create_new_ref_number,
                        max_length=10,
                        unique=True,
                    ),
                ),
                ("title", models.CharField(max_length=200)),
                (
                    "description",
                    models.CharField(blank=True, max_length=2000, null=True),
                ),
                (
                    "hourly_rate",
                    models.IntegerField(
                        default=50,
                        validators=[django.core.validators.MinValueValidator(1)],
                    ),
                ),
                ("email_recipient_name", models.CharField(max_length=200)),
                ("email_recipient", models.EmailField(max_length=254)),
                (
                    "invoice_interval",
                    models.CharField(
                        choices=[
                            ("D", "DAILY"),
                            ("W", "WEEKLY"),
                            ("B", "BIWEEKLY"),
                            ("M", "MONTHLY"),
                            ("Q", "QUARTERLY"),
                            ("Y", "YEARLY"),
                        ],
                        default="M",
                        max_length=1,
                    ),
                ),
                ("next_date", models.DateField(blank=True, null=True)),
                ("last_date", models.DateField(blank=True, null=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="invoices",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "quickbooks_customer_ref_id",
                    models.CharField(blank=True, max_length=200, null=True),
                ),
                (
                    "freshbooks_client_id",
                    models.CharField(blank=True, max_length=200, null=True),
                ),
                (
                    "is_archived",
                    models.BooleanField(blank=True, default=False, null=True),
                ),
                ("total_budget", models.IntegerField(blank=True, null=True)),
                (
                    "xero_contact_id",
                    models.CharField(blank=True, max_length=200, null=True),
                ),
                (
                    "zoho_contact_id",
                    models.CharField(blank=True, max_length=200, null=True),
                ),
                (
                    "zoho_contact_persons_id",
                    models.CharField(blank=True, max_length=200, null=True),
                ),
                (
                    "sage_contact_id",
                    models.CharField(blank=True, max_length=200, null=True),
                ),
                (
                    "email_recipient_stripe_customer_id",
                    models.CharField(blank=True, max_length=200, null=True),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="DailyHoursInput",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        db_index=True,
                        default=uuid.uuid4,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "hours",
                    models.DecimalField(
                        decimal_places=1,
                        default=1,
                        max_digits=3,
                        validators=[
                            timary.models.validate_less_than_24_hours,
                            timary.models.validate_greater_than_zero_hours,
                        ],
                    ),
                ),
                ("notes", models.CharField(blank=True, max_length=2000, null=True)),
                ("date_tracked", models.DateField()),
                (
                    "invoice",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="hours_tracked",
                        to="timary.invoice",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.AlterModelManagers(
            name="dailyhoursinput",
            managers=[],
        ),
        migrations.AlterField(
            model_name="dailyhoursinput",
            name="hours",
            field=models.DecimalField(
                decimal_places=2,
                default=1,
                max_digits=4,
                validators=[
                    timary.models.validate_less_than_24_hours,
                    timary.models.validate_greater_than_zero_hours,
                ],
            ),
        ),
        migrations.CreateModel(
            name="SentInvoice",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        db_index=True,
                        default=uuid.uuid4,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("hours_start_date", models.DateField(blank=True, null=True)),
                ("hours_end_date", models.DateField(blank=True, null=True)),
                ("date_sent", models.DateField()),
                ("total_price", models.PositiveIntegerField()),
                (
                    "paid_status",
                    models.PositiveSmallIntegerField(
                        choices=[(1, "PENDING"), (2, "PAID")], default=1
                    ),
                ),
                (
                    "invoice",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="invoice_snapshots",
                        to="timary.invoice",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sent_invoices",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "quickbooks_invoice_id",
                    models.CharField(blank=True, max_length=200, null=True),
                ),
                (
                    "freshbooks_invoice_id",
                    models.CharField(blank=True, max_length=200, null=True),
                ),
                (
                    "xero_invoice_id",
                    models.CharField(blank=True, max_length=200, null=True),
                ),
                (
                    "zoho_invoice_id",
                    models.CharField(blank=True, max_length=200, null=True),
                ),
                (
                    "sage_invoice_id",
                    models.CharField(blank=True, max_length=200, null=True),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.AddField(
            model_name="sentinvoice",
            name="stripe_payment_intent_id",
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AlterField(
            model_name="sentinvoice",
            name="paid_status",
            field=models.PositiveSmallIntegerField(
                choices=[(1, "PENDING"), (2, "PAID"), (3, "FAILED")], default=1
            ),
        ),
    ]