# Generated by Django 3.2.8 on 2021-12-05 20:44

import uuid

import django.contrib.auth.models
import django.contrib.auth.validators
import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

import timary.models


class Migration(migrations.Migration):

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
                    models.CharField(blank=True, max_length=16, null=True, unique=True),
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
    ]
