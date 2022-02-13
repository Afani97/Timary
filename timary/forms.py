import datetime

from django.contrib.auth.forms import forms
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
            invoice_qs = Invoice.objects.filter(user=user)
            if invoice_qs.count() > 0:
                self.fields["invoice"].queryset = invoice_qs
                self.fields["invoice"].initial = invoice_qs.first()

    class Meta:
        model = DailyHoursInput
        fields = ["hours", "date_tracked", "invoice"]
        widgets = {
            "hours": forms.NumberInput(
                attrs={
                    "value": 1.0,
                    "max": 24,
                    "min": -1,
                    "step": 0.01,
                }
            ),
            "date_tracked": DateInput(
                attrs={
                    "value": datetime.date.today(),
                    "max": datetime.date.today(),
                }
            ),
            "invoice": forms.Select(attrs={"label": "Invoice"}),
            "notes": forms.Textarea(attrs={"rows": 4, "cols": 30, "collapse": True}),
        }

    field_order = ["hours", "date_tracked", "invoice"]

    def clean_date_tracked(self):
        date_tracked = self.cleaned_data.get("date_tracked")
        if date_tracked > datetime.date.today():
            raise ValidationError("Cannot set date into the future!")
        return date_tracked


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = [
            "title",
            "hourly_rate",
            "invoice_interval",
            "email_recipient_name",
            "email_recipient",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "placeholder": "New Saas App...",
                }
            ),
            "hourly_rate": forms.NumberInput(
                attrs={
                    "value": 50,
                    "min": 1,
                    "max": 1000,
                }
            ),
            "invoice_interval": forms.Select(attrs={"label": "Invoice"}),
            "email_recipient_name": forms.TextInput(attrs={"placeholder": "John"}),
            "email_recipient": forms.EmailInput(
                attrs={"placeholder": "john@company.com"}
            ),
        }

    def clean_email_recipient_name(self):
        email_recipient_name = self.cleaned_data.get("email_recipient_name")
        if not all(x.isalpha() or x.isspace() for x in email_recipient_name):
            raise ValidationError("Only valid names allowed.")
        return email_recipient_name


class PayInvoiceForm(forms.Form):
    email = forms.EmailField(
        label="Your email",
        widget=forms.TextInput(
            attrs={"placeholder": "john@appleseed.com", "classes": "col-span-2"}
        ),
    )
    first_name = forms.CharField(
        label="Your first name",
        widget=forms.TextInput(attrs={"placeholder": "John", "classes": "col-span-2"}),
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
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=True)
    phone_number = forms.CharField(
        required=False,
        validators=[phone_number_regex],
        widget=forms.TextInput(attrs={"placeholder": "+13334445555"}),
    )

    class Meta:
        model = User
        fields = ["email", "first_name", "last_name", "phone_number", "membership_tier"]
        widgets = {
            "email": forms.TextInput(attrs={"placeholder": "john@appleseed.com"}),
            "first_name": forms.TextInput(attrs={"placeholder": "John"}),
            "last_name": forms.TextInput(attrs={"placeholder": "Appleseed"}),
        }
        labels = {"membership_tier": "Subscription plan"}

    field_order = [
        "first_name",
        "last_name",
        "email",
        "phone_number",
        "membership_tier",
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


class SettingsForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["phone_number_availability"]


class RegisterForm(forms.ModelForm):
    email = forms.EmailField(
        label="Email",
        required=True,
        widget=forms.TextInput(attrs={"placeholder": "example@test.com"}),
    )
    full_name = forms.CharField(
        label="Full name",
        required=True,
        widget=forms.TextInput(attrs={"placeholder": "Tom Brady"}),
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(
            attrs={"placeholder": "*********", "type": "password"}
        ),
        required=True,
    )

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
        labels = {"membership_tier": "Subscription Plan"}


class LoginForm(forms.Form):
    email = forms.EmailField(
        label="Email",
        required=True,
        widget=forms.EmailInput(attrs={"placeholder": "tom@test.com"}),
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(
            attrs={"placeholder": "*********", "type": "password"}
        ),
        required=True,
    )

    class Meta:
        fields = ["email", "password"]
