import datetime

from django.contrib.auth.forms import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from timary.models import DailyHoursInput, Invoice


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
        if not email_recipient_name.isalpha():
            raise ValidationError("Only valid names allowed.")
        return email_recipient_name


class DateInput(forms.DateInput):
    input_type = "date"


class DailyHoursForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        userprofile = kwargs.pop("userprofile") if "userprofile" in kwargs else None

        super(DailyHoursForm, self).__init__(*args, **kwargs)

        if userprofile:
            invoice_qs = Invoice.objects.filter(user=userprofile)
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
                    "min": 1,
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


class UserProfileForm(forms.ModelForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=True)

    class Meta:
        model = User
        fields = ["email", "first_name", "last_name"]
        widgets = {
            "email": forms.TextInput(attrs={"placeholder": "john@appleseed.com"}),
            "first_name": forms.TextInput(attrs={"placeholder": "John"}),
            "last_name": forms.TextInput(attrs={"placeholder": "Appleseed"}),
        }

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


class RegisterForm(forms.ModelForm):
    email = forms.EmailField(
        label="Email",
        required=True,
        widget=forms.TextInput(attrs={"placeholder": "example@test.com"}),
    )
    first_name = forms.CharField(
        label="First name",
        required=True,
        widget=forms.TextInput(attrs={"placeholder": "Tom"}),
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(
            attrs={"placeholder": "*********", "type": "password"}
        ),
        required=True,
    )

    def clean_first_name(self):
        first_name = self.cleaned_data.get("first_name")
        if not first_name.isalpha():
            raise ValidationError("Only valid names allowed.")
        return first_name

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if User.objects.filter(username=email).count() != 0:
            raise ValidationError("Email already registered!")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user

    class Meta:
        model = User
        fields = (
            "first_name",
            "email",
            "password",
        )


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
