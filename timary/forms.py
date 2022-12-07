import datetime

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

from timary.models import DailyHoursInput, Invoice, User


class DateInput(forms.DateInput):
    input_type = "date"


class DailyHoursForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user") if "user" in kwargs else None

        super(DailyHoursForm, self).__init__(*args, **kwargs)

        if user:
            invoice_qs = user.get_invoices
            if invoice_qs.count() > 0:
                self.fields["invoice"].queryset = invoice_qs
                self.fields["invoice"].initial = invoice_qs.first()

        # Set date_tracked value/max when form is initialized
        self.fields["date_tracked"].widget.attrs["value"] = datetime.date.today()
        self.fields["date_tracked"].widget.attrs["max"] = datetime.date.today()
        if self.initial and self.instance.invoice:
            self.fields["date_tracked"].widget.attrs[
                "min"
            ] = self.instance.invoice.last_date

    class Meta:
        model = DailyHoursInput
        fields = ["hours", "date_tracked", "invoice"]
        widgets = {
            "hours": forms.TextInput(
                attrs={
                    "value": 1.0,
                    "class": "input input-bordered border-2 text-lg hours-input w-full",
                    "_": "on input call filterHoursInput(me) end on blur call convertHoursInput(me) end",
                },
            ),
            "date_tracked": DateInput(
                attrs={
                    "class": "input input-bordered border-2 text-lg w-full",
                }
            ),
            "invoice": forms.Select(
                attrs={
                    "label": "Invoice",
                    "class": "select select-bordered border-2 w-full",
                }
            ),
        }

    field_order = ["hours", "date_tracked", "invoice"]

    def clean_date_tracked(self):
        date_tracked = self.cleaned_data.get("date_tracked")
        if date_tracked > datetime.date.today():
            raise ValidationError("Cannot set date into the future!")
        return date_tracked

    def clean_hours(self):
        hours = self.cleaned_data.get("hours")
        try:
            hours_float = float(hours)
        except ValueError:
            raise ValidationError(
                "Invalid hours logged. Please log between 0 and 24 hours"
            )
        if 0 < hours_float <= 24:
            return hours
        else:
            raise ValidationError(
                "Invalid hours logged. Please log between 0 and 24 hours"
            )

    def clean(self):
        validated_data = super().clean()

        date_tracked = validated_data.get("date_tracked")
        invoice = validated_data.get("invoice")
        if date_tracked and invoice and invoice.last_date:
            if date_tracked < invoice.last_date:
                raise ValidationError(
                    "Cannot set date since your last invoice's cutoff date."
                )

        return validated_data


class InvoiceForm(forms.ModelForm):
    # Don't require budget in create form
    total_budget = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(
            attrs={
                "min": 1,
                "max": 1_000_000,
                "class": "input input-bordered border-2 text-lg w-full",
                "placeholder": "10000",
            }
        ),
    )
    milestone_total_steps = forms.IntegerField(
        widget=forms.NumberInput(
            attrs={
                "placeholder": 3,
                "min": 2,
                "max": 12,
                "class": "input input-bordered border-2 text-lg w-full",
            }
        ),
    )
    weekly_rate = forms.IntegerField(
        widget=forms.NumberInput(
            attrs={
                "placeholder": 1200,
                "min": 100,
                "class": "input input-bordered border-2 text-lg w-full",
            }
        ),
    )
    start_on = forms.DateField(
        required=False,
        widget=DateInput(
            attrs={
                "class": "input input-bordered border-2 text-lg w-full",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user") if "user" in kwargs else None
        super(InvoiceForm, self).__init__(*args, **kwargs)
        self.fields["invoice_rate"].label = "Hourly rate"
        if not self.initial:
            self.fields["invoice_interval"].required = False
            self.fields["milestone_total_steps"].required = False
            self.fields["weekly_rate"].required = False
            self.fields["milestone_total_steps"].widget.attrs[
                "_"
            ] = "on load add .hidden .invoice-type .invoice-type-2 to the closest .form-control"
            self.fields["weekly_rate"].widget.attrs["_"] = (
                "on load add .hidden .invoice-type .invoice-type-3 to the closest .form-control end "
                "on intersection(intersecting) having threshold 1 "
                "if intersecting add .hidden to #id_invoice_rate's parentNode's parentNode "
                "else remove .hidden from #id_invoice_rate's parentNode's parentNode end "
            )
        if self.initial:
            # Problems of dealing with dynamic selects + show/hide certain fields.
            self.fields["invoice_type"].required = False
            if self.instance.invoice_type == Invoice.InvoiceType.MILESTONE:
                self.fields["invoice_interval"].required = False
                self.fields["weekly_rate"].required = False
            if self.instance.invoice_type == Invoice.InvoiceType.INTERVAL:
                self.fields["milestone_total_steps"].required = False
                self.fields["weekly_rate"].required = False
            if self.instance.invoice_type == Invoice.InvoiceType.WEEKLY:
                self.fields["weekly_rate"].initial = self.instance.invoice_rate
                self.fields["invoice_interval"].required = False
                self.fields["milestone_total_steps"].required = False

    class Meta:
        model = Invoice
        fields = [
            "title",
            "invoice_rate",
            "total_budget",
            "invoice_type",
            "invoice_interval",
            "milestone_total_steps",
            "weekly_rate",
            "email_recipient_name",
            "email_recipient",
            "start_on",
        ]
        labels = {
            "email_recipient_name": "Client's name",
            "email_recipient": "Client's email",
        }
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "placeholder": "New Saas App...",
                    "class": "input input-bordered border-2 text-lg w-full",
                }
            ),
            "invoice_rate": forms.NumberInput(
                attrs={
                    "value": 50,
                    "min": 1,
                    "max": 1000,
                    "class": "input input-bordered border-2 text-lg w-full",
                },
            ),
            "invoice_type": forms.Select(
                attrs={
                    "label": "Invoice",
                    "class": "select select-bordered border-2 text-lg w-full",
                    "_": "on change set inv_type to `invoice-type-${my.value}` then "
                    "add .hidden to .invoice-type then remove .hidden from .{inv_type}",
                }
            ),
            "invoice_interval": forms.Select(
                attrs={
                    "label": "Invoice",
                    "class": "select select-bordered border-2 text-lg w-full",
                    "_": "on load add .invoice-type .invoice-type-1 to the closest .form-control",
                }
            ),
            "email_recipient_name": forms.TextInput(
                attrs={
                    "placeholder": "John Smith",
                    "class": "input input-bordered border-2 text-lg w-full",
                }
            ),
            "email_recipient": forms.EmailInput(
                attrs={
                    "placeholder": "john@company.com",
                    "class": "input input-bordered border-2 text-lg w-full",
                }
            ),
        }

    def clean(self):
        validated_data = super().clean()

        invoice_type = validated_data.get("invoice_type")
        invoice_interval = validated_data.get("invoice_interval")
        milestone_total_steps = validated_data.get("milestone_total_steps")
        weekly_rate = validated_data.get("weekly_rate")

        if "start_on" in validated_data:
            start_on = validated_data.get("start_on", None)
            if start_on and start_on < datetime.date.today():
                raise ValidationError(
                    {"start_on": ["Cannot start invoice less than today."]}
                )
        if invoice_type == 1 and not invoice_interval:
            raise ValidationError(
                {"invoice_interval": ["Invoice interval is required"]}
            )
        if invoice_type == 2 and not milestone_total_steps:
            raise ValidationError(
                {"milestone_total_steps": ["Milestone total steps is required"]}
            )
        if invoice_type == 3 and not weekly_rate:
            raise ValidationError({"weekly_rate": ["Weekly rate is required"]})

        return validated_data

    def clean_email_recipient_name(self):
        email_recipient_name = self.cleaned_data.get("email_recipient_name")
        if not all(x.isalpha() or x.isspace() for x in email_recipient_name):
            raise ValidationError("Only valid names allowed.")
        return email_recipient_name

    def clean_title(self):
        title = self.cleaned_data.get("title")
        if (
            self.user
            and self.user.get_invoices.count() > 0
            and self.instance.title != title
            and self.user.get_invoices.filter(title=title).exists()
        ):
            raise ValidationError("Duplicate invoice title not allowed.")
        if title[0].isdigit():
            raise ValidationError("Title cannot start with a number.")
        return title

    def clean_milestone_total_steps(self):
        total_steps = self.cleaned_data.get("milestone_total_steps")
        if (
            self.instance
            and self.instance.invoice_type == Invoice.InvoiceType.MILESTONE
            and self.instance.milestone_step
        ):
            if total_steps < self.instance.milestone_step:
                raise ValidationError(
                    "Cannot set milestone total steps to less than what is already completed"
                )
        return total_steps


class PayInvoiceForm(forms.Form):
    email = forms.EmailField(
        label="Confirm your email",
        widget=forms.TextInput(
            attrs={
                "placeholder": "john@appleseed.com",
                "classes": "col-span-2",
                "class": "input input-bordered border-2 text-lg bg-neutral "
                "focus:border-primary focus:ring-0 focus:ring-primary w-full",
            }
        ),
    )
    first_name = forms.CharField(
        label="Confirm your first name",
        widget=forms.TextInput(
            attrs={
                "placeholder": "John",
                "classes": "col-span-2",
                "class": "input input-bordered border-2 text-lg bg-neutral "
                "focus:border-primary focus:ring-0 focus:ring-primary w-full",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        self.sent_invoice = (
            kwargs.pop("sent_invoice") if "sent_invoice" in kwargs else None
        )
        super(PayInvoiceForm, self).__init__(*args, **kwargs)

    def clean_email(self):
        cleaned_email = self.cleaned_data.get("email")
        if (
            cleaned_email.lower().strip()
            != self.sent_invoice.invoice.email_recipient.lower()
        ):
            raise ValidationError(
                "Unable to process payment, please enter correct details."
            )

    def clean_first_name(self):
        cleaned_name = self.cleaned_data.get("first_name")
        if (
            cleaned_name.lower().strip()
            not in self.sent_invoice.invoice.email_recipient_name.lower()
        ):
            raise ValidationError(
                "Unable to process payment, please enter correct details."
            )


phone_number_regex = RegexValidator(
    regex=r"^\+?1?\d{8,15}$", message="Wrong format, needs to be: +13334445555"
)


class UserForm(forms.ModelForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={
                "placeholder": "john@appleseed.com",
                "class": "input input-bordered border-2 text-lg w-full",
            }
        ),
    )
    first_name = forms.CharField(
        required=True,
        widget=forms.TextInput(
            attrs={
                "placeholder": "John",
                "class": "input input-bordered border-2 text-lg w-full",
            }
        ),
    )
    last_name = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Appleseed",
                "class": "input input-bordered border-2 text-lg w-full",
            }
        ),
    )
    phone_number = forms.CharField(
        required=False,
        validators=[phone_number_regex],
        widget=forms.TextInput(
            attrs={
                "placeholder": "+13334445555",
                "class": "input input-bordered border-2 text-lg w-full",
            }
        ),
    )
    profile_pic = forms.ImageField(required=False)

    class Meta:
        model = User
        fields = ["email", "first_name", "last_name", "phone_number", "profile_pic"]

    field_order = [
        "profile_pic",
        "first_name",
        "last_name",
        "email",
        "phone_number",
    ]

    def clean_first_name(self):
        first_name = self.cleaned_data.get("first_name")
        if not first_name.isalpha():
            raise ValidationError("Only valid names allowed.")
        return first_name

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if (
            email != self.instance.email
            and User.objects.filter(username=email, email=email).count() != 0
        ):
            raise ValidationError("Email already registered!")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = user.email
        if commit:
            user.save()
        return user


class SMSSettingsForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["phone_number_availability"]


def validate_due_date_integer(val):
    """Valid values are 1, 2, 4, corresponding to weeks"""
    if val not in [1, 2, 4]:
        raise ValidationError("Invalid due date value")
    return val


class InvoiceBrandingSettingsForm(forms.Form):
    due_date = forms.IntegerField(
        validators=[validate_due_date_integer], required=False
    )
    company_name = forms.CharField(max_length=50, required=False)
    hide_timary = forms.BooleanField(required=False)
    show_profile_pic = forms.BooleanField(required=False)
    personal_website = forms.CharField(required=False)
    linked_in = forms.CharField(required=False)
    twitter = forms.CharField(required=False)
    youtube = forms.CharField(required=False)


class RegisterForm(forms.ModelForm):
    email = forms.EmailField(
        label="Email",
        required=True,
        widget=forms.TextInput(
            attrs={
                "placeholder": "john@appleseed.com",
                "class": "input input-bordered border-2 text-lg w-full mb-4",
            }
        ),
    )
    full_name = forms.CharField(
        label="Full name",
        required=True,
        widget=forms.TextInput(
            attrs={
                "placeholder": "John Appleseed",
                "class": "input input-bordered border-2 text-lg w-full mb-4",
            }
        ),
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "*********",
                "type": "password",
                "class": "input input-bordered border-2 text-lg w-full mb-4",
            },
        ),
        help_text="Please provide at least 5 characters including 1 uppercase, 1 number, 1 special character.",
        required=True,
    )

    def clean_full_name(self):
        full_name = self.cleaned_data.get("full_name")
        if not full_name.replace(" ", "").isalpha():
            raise ValidationError("Only valid names allowed.")
        return full_name

    def clean(self):
        validate_data = super().clean()
        email = validate_data.get("email")
        if User.objects.filter(username=email).count() != 0:
            raise ValidationError(
                "We're having trouble creating your account. Please try again"
            )
        return validate_data

    def save(self, commit=True):
        user = super().save(commit=False)
        first_name, last_name = self.cleaned_data.get("full_name").split(" ")
        user.first_name = first_name
        user.last_name = last_name
        user.set_password(self.cleaned_data["password"])
        user.username = self.cleaned_data["email"]
        user.phone_number_availability = ["Mon", "Tue", "Wed", "Thu", "Fri"]
        if commit:
            user.save()
        return user

    class Meta:
        model = User
        fields = (
            "full_name",
            "email",
            "password",
        )


class LoginForm(forms.Form):
    email = forms.EmailField(
        label="Email",
        required=True,
        widget=forms.EmailInput(
            attrs={
                "placeholder": "johns@awesomeemail.com",
                "class": "input input-bordered border-2 text-lg w-full mb-4",
            }
        ),
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "*********",
                "type": "password",
                "class": "input input-bordered border-2 text-lg w-full",
            }
        ),
        required=True,
    )

    class Meta:
        fields = ["email", "password"]


class QuestionsForm(forms.Form):
    question = forms.CharField(required=True)

    class Meta:
        fields = ["question"]


class ContractForm(forms.Form):
    contractor_name = forms.CharField(label="Your Name")
    contractor_address = forms.CharField(label="Your Address")
    contractor_email = forms.CharField(label="Your Email")
    contractor_signature = forms.CharField(label="Your Signature")
    client_name = forms.CharField(label="Client Name")
    client_address = forms.CharField(label="Client Address")
    client_email = forms.CharField(label="Client Email")
    service_description = forms.CharField(required=False)
    project_budget = forms.CharField(required=False)
    start_date = forms.DateField(required=False)
    end_date = forms.DateField(required=False)
    state_work = forms.CharField(required=False)

    class Meta:
        fields = ["__all__"]


class ReferralInviteForm(forms.Form):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={
                "class": "input input-bordered border-2 w-full",
                "placeholder": "Enter email here",
            }
        ),
    )

    class Meta:
        fields = ["email"]


class UpdatePasswordForm(forms.Form):
    current_password = forms.CharField(
        label="Current Password",
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "*********",
                "type": "password",
                "class": "input input-bordered border-2 text-lg w-full",
            }
        ),
        required=True,
    )
    new_password = forms.CharField(
        label="New Password",
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "*********",
                "type": "password",
                "class": "input input-bordered border-2 text-lg w-full",
            }
        ),
        required=True,
    )

    class Meta:
        fields = ["current_password", "new_password"]

    def __init__(self, *args, **kwargs):
        self.user: User = kwargs.pop("user") if "user" in kwargs else None
        super().__init__(*args, **kwargs)

    def clean(self):
        validated_data = super().clean()

        current_password = validated_data.get("current_password")
        if not self.user.check_password(current_password):
            raise ValidationError("Unable to update password")

        return validated_data
