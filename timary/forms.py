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
                attrs={"placeholder": "New Saas App...", "classes": "col-span-5"}
            ),
            "hourly_rate": forms.NumberInput(
                attrs={"value": 50, "min": 1, "max": 1000, "classes": "col-span-2"}
            ),
            "invoice_interval": forms.Select(
                attrs={"label": "Invoice", "classes": "col-span-2"}
            ),
            "email_recipient_name": forms.TextInput(
                attrs={"placeholder": "John", "classes": "col-span-3"}
            ),
            "email_recipient": forms.TextInput(
                attrs={"placeholder": "john@company.com", "classes": "col-span-3"}
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
        labels = {"invoice": "Invoice"}
        widgets = {
            "hours": forms.NumberInput(
                attrs={"value": 1, "max": 23.5, "min": 0.5, "classes": "col-span-1"}
            ),
            "date_tracked": DateInput(
                attrs={"value": datetime.date.today(), "classes": "col-span-2"}
            ),
            "invoice": forms.Select(
                attrs={"label": "Invoice", "classes": "col-span-2"}
            ),
            "notes": forms.Textarea(
                attrs={"rows": 4, "cols": 30, "collapse": True, "classes": "col-span-5"}
            ),
        }

    field_order = ["hours", "date_tracked", "invoice"]


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
