import datetime

from crispy_forms.helper import FormHelper
from django.contrib.auth.forms import forms
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

from timary.form_helpers import (
    invoice_form_helper,
    login_form_helper,
    profile_form_helper,
    register_form_helper,
)
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

    class Meta:
        model = DailyHoursInput
        fields = ["hours", "date_tracked", "invoice"]
        widgets = {
            "hours": forms.TextInput(
                attrs={
                    "value": 1.0,
                    "class": "input input-bordered text-lg hours-input w-full",
                    "_": "on input call filterHoursInput(me) end on blur call convertHoursInput(me) end",
                },
            ),
            "date_tracked": DateInput(
                attrs={
                    "class": "input input-bordered text-lg w-full",
                }
            ),
            "invoice": forms.Select(
                attrs={
                    "label": "Invoice",
                    "class": "select select-bordered w-full",
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
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user") if "user" in kwargs else None
        is_mobile = kwargs.pop("is_mobile") if "is_mobile" in kwargs else False
        request_method = (
            kwargs.pop("request_method").lower()
            if "request_method" in kwargs
            else "get"
        )

        super(InvoiceForm, self).__init__(*args, **kwargs)

        num_invoices = self.user.get_invoices.count() if self.user else 0

        self.helper = FormHelper(self)
        self.helper._form_method = ""
        self.helper.form_show_errors = False
        helper_attributes = invoice_form_helper(
            request_method, is_mobile, self.instance, num_invoices != 0
        )
        for key in helper_attributes:
            setattr(self.helper, key, helper_attributes[key])

    class Meta:
        model = Invoice
        fields = [
            "title",
            "hourly_rate",
            "invoice_interval",
            "total_budget",
            "email_recipient_name",
            "email_recipient",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "placeholder": "New Saas App...",
                    "class": "input input-bordered text-lg w-full",
                }
            ),
            "hourly_rate": forms.NumberInput(
                attrs={
                    "value": 50,
                    "min": 1,
                    "max": 1000,
                    "class": "input input-bordered text-lg w-full",
                }
            ),
            "total_budget": forms.NumberInput(
                attrs={
                    "min": 1,
                    "max": 1_000_000,
                    "class": "input input-bordered text-lg w-full",
                    "placeholder": "10000",
                }
            ),
            "invoice_interval": forms.Select(
                attrs={
                    "label": "Invoice",
                    "class": "select select-bordered text-lg w-full",
                }
            ),
            "email_recipient_name": forms.TextInput(
                attrs={
                    "placeholder": "John Smith",
                    "class": "input input-bordered text-lg w-full",
                }
            ),
            "email_recipient": forms.EmailInput(
                attrs={
                    "placeholder": "john@company.com",
                    "class": "input input-bordered text-lg w-full",
                }
            ),
        }

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


class PayInvoiceForm(forms.Form):
    email = forms.EmailField(
        label="Confirm your email",
        widget=forms.TextInput(
            attrs={
                "placeholder": "john@appleseed.com",
                "classes": "col-span-2",
                "class": "input input-bordered text-lg bg-neutral "
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
                "class": "input input-bordered text-lg bg-neutral "
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
            raise ValidationError("Wrong email recipient, unable to process payment")

    def clean_first_name(self):
        cleaned_name = self.cleaned_data.get("first_name")
        if (
            cleaned_name.lower().strip()
            not in self.sent_invoice.invoice.email_recipient_name.lower()
        ):
            raise ValidationError("Wrong name recipient, unable to process payment")


phone_number_regex = RegexValidator(
    regex=r"^\+?1?\d{8,15}$", message="Wrong format, needs to be: +13334445555"
)


class UserForm(forms.ModelForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={
                "placeholder": "john@appleseed.com",
                "class": "input input-bordered text-lg w-full",
            }
        ),
    )
    first_name = forms.CharField(
        required=True,
        widget=forms.TextInput(
            attrs={
                "placeholder": "John",
                "class": "input input-bordered text-lg w-full",
            }
        ),
    )
    last_name = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Appleseed",
                "class": "input input-bordered text-lg w-full",
            }
        ),
    )
    phone_number = forms.CharField(
        required=False,
        validators=[phone_number_regex],
        widget=forms.TextInput(
            attrs={
                "placeholder": "+13334445555",
                "class": "input input-bordered text-lg w-full",
            }
        ),
    )
    profile_pic = forms.ImageField(required=False)

    def __init__(self, *args, **kwargs):
        is_mobile = kwargs.pop("is_mobile") if "is_mobile" in kwargs else False

        super(UserForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper(self)
        self.helper._form_method = ""
        self.helper.form_show_errors = False
        helper_attributes = profile_form_helper(is_mobile)
        for key in helper_attributes:
            setattr(self.helper, key, helper_attributes[key])

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


class MembershipTierSettingsForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["membership_tier"]


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
                "class": "input input-bordered text-lg w-full",
            }
        ),
    )
    full_name = forms.CharField(
        label="Full name",
        required=True,
        widget=forms.TextInput(
            attrs={
                "placeholder": "John Appleseed",
                "class": "input input-bordered text-lg w-full",
            }
        ),
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "*********",
                "type": "password",
                "class": "input input-bordered text-lg w-full",
            }
        ),
        required=True,
    )
    membership_tier = forms.CharField(
        widget=forms.HiddenInput(
            attrs={"id": "hidden-membership", "name": "hidden-membership"}
        ),
        required=True,
    )

    def __init__(self, *args, **kwargs):
        super(RegisterForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper(self)
        self.helper.form_method = "post"
        self.helper.form_show_errors = False
        helper_attributes = register_form_helper()
        for key in helper_attributes:
            setattr(self.helper, key, helper_attributes[key])

    def clean_full_name(self):
        full_name = self.cleaned_data.get("full_name")
        if not full_name.replace(" ", "").isalpha():
            raise ValidationError("Only valid names allowed.")
        return full_name

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if User.objects.filter(username=email).count() != 0:
            raise ValidationError("Error creating account")
        return email

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
            "membership_tier",
        )


class LoginForm(forms.Form):
    email = forms.EmailField(
        label="Email",
        required=True,
        widget=forms.EmailInput(
            attrs={
                "placeholder": "johns@awesomeemail.com",
                "class": "input input-bordered text-lg w-full mb-4",
            }
        ),
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "*********",
                "type": "password",
                "class": "input input-bordered text-lg w-full",
            }
        ),
        required=True,
    )

    def __init__(self, *args, **kwargs):
        super(LoginForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper(self)
        self.helper.form_method = "post"
        self.helper.form_show_errors = False
        helper_attributes = login_form_helper()
        for key in helper_attributes:
            setattr(self.helper, key, helper_attributes[key])

    class Meta:
        fields = ["email", "password"]


class QuestionsForm(forms.Form):
    question = forms.CharField(required=True)

    class Meta:
        fields = ["question"]


class ContractForm(forms.Form):
    first_name = forms.CharField(required=False)
    last_name = forms.CharField(required=False)
    street_address = forms.CharField(required=False)
    city = forms.CharField(required=False)
    state = forms.CharField(required=False)
    email = forms.CharField(required=False)
    client_first_name = forms.CharField(required=False)
    client_last_name = forms.CharField(required=False)
    client_street_address = forms.CharField(required=False)
    client_city = forms.CharField(required=False)
    client_state = forms.CharField(required=False)
    client_email = forms.CharField(required=False)
    service_description = forms.CharField(required=False)
    project_budget = forms.CharField(required=False)
    start_date = forms.DateField(required=False)
    end_date = forms.DateField(required=False)
    state_work = forms.CharField(required=False)

    class Meta:
        fields = ["__all__"]
