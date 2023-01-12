import datetime

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from phonenumber_field.formfields import PhoneNumberField

from timary.models import (
    HoursLineItem,
    IntervalInvoice,
    Invoice,
    MilestoneInvoice,
    RecurringInvoice,
    User,
    WeeklyInvoice,
)
from timary.utils import get_starting_week_from_date


class DateInput(forms.DateInput):
    input_type = "date"


class HoursLineItemForm(forms.ModelForm):
    repeating = forms.BooleanField(required=False, initial=False)
    recurring = forms.BooleanField(required=False, initial=False)
    repeat_end_date = forms.DateField(
        required=False,
    )
    repeat_interval_schedule = forms.ChoiceField(
        required=False,
        choices=[("d", "Daily"), ("w", "Weekly"), ("b", "Biweekly")],
    )
    repeat_interval_days = forms.MultipleChoiceField(
        required=False,
        choices=[
            ("sun", "Sunday"),
            ("mon", "Monday"),
            ("tue", "Tuesday"),
            ("wed", "Wednesday"),
            ("thu", "Thursday"),
            ("fri", "Friday"),
            ("sat", "Saturday"),
        ],
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user") if "user" in kwargs else None

        super(HoursLineItemForm, self).__init__(*args, **kwargs)

        if user:
            invoice_qs = user.get_invoices.filter(is_paused=False)
            if invoice_qs.count() > 0:
                self.fields["invoice"].queryset = invoice_qs
                self.fields["invoice"].initial = invoice_qs.first()
            else:
                self.fields["invoice"].queryset = RecurringInvoice.objects.none()

        # Set date_tracked value/max when form is initialized
        self.fields["date_tracked"].widget.attrs["value"] = datetime.date.today()
        self.fields["date_tracked"].widget.attrs["max"] = datetime.date.today()
        if (
            self.initial
            and self.instance.invoice
            and hasattr(self.instance.invoice, "last_date")
        ):
            self.fields["date_tracked"].widget.attrs[
                "min"
            ] = self.instance.invoice.last_date
            self.fields["quantity"].widget.attrs["id"] = f"id_{self.instance.slug_id}"

    class Meta:
        model = HoursLineItem
        fields = ["quantity", "date_tracked", "invoice"]
        labels = {"quantity": "Hours"}
        widgets = {
            "quantity": forms.TextInput(
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

    field_order = ["quantity", "date_tracked", "invoice"]

    def clean_date_tracked(self):
        date_tracked = self.cleaned_data.get("date_tracked")
        if date_tracked > datetime.date.today():
            raise ValidationError("Cannot set date into the future!")
        return date_tracked

    def clean_quantity(self):
        hours = self.cleaned_data.get("quantity")
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
        if date_tracked and invoice and hasattr(invoice, "last_date"):
            if date_tracked < invoice.last_date:
                raise ValidationError(
                    "Cannot set date since your last invoice's cutoff date."
                )

        repeating = validated_data.get("repeating")
        recurring = validated_data.get("recurring")
        repeat_end_date = validated_data.get("repeat_end_date")
        interval_schedule = validated_data.get("repeat_interval_schedule")
        interval_days = validated_data.get("repeat_interval_days")

        if repeating and recurring:
            raise ValidationError("Cannot set repeating and recurring both to true.")
        if repeating and not repeat_end_date:
            raise ValidationError("Cannot have a repeating hour without an end date.")
        if repeating and repeat_end_date and repeat_end_date < datetime.date.today():
            raise ValidationError("Cannot set repeat end date less than today.")
        if recurring and repeat_end_date:
            validated_data.pop("repeat_end_date")
        if interval_schedule in ["w", "b"] and not interval_days:
            raise ValidationError("Need specific days which to add hours to.")

        if repeating or recurring:
            starting_week_date = date_tracked
            if date_tracked.weekday() == 5:
                # If date is saturday, set it to sunday to update start_week
                # If interval_schedule is biweekly, set it to the sunday after the next
                days_ahead = 1 if interval_schedule != "b" else 8
                starting_week_date = starting_week_date + datetime.timedelta(
                    days=days_ahead
                )
            recurring_logic = {
                "type": "recurring",
                "interval": interval_schedule,
                "interval_days": interval_days,
                "starting_week": get_starting_week_from_date(
                    starting_week_date
                ).isoformat(),
            }
            if repeating:
                recurring_logic.update(
                    {"type": "repeating", "end_date": repeat_end_date.isoformat()}
                )
            validated_data["recurring_logic"] = recurring_logic

        return validated_data


class InvoiceForm(forms.ModelForm):
    rate = forms.DecimalField(
        required=True,
        widget=forms.NumberInput(
            attrs={
                "value": 50,
                "min": 1,
                "max": 1000,
                "step": "0.01",
                "class": "input input-bordered border-2 text-lg w-full",
            },
        ),
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user") if "user" in kwargs else None
        super(InvoiceForm, self).__init__(*args, **kwargs)

    class Meta:
        model = Invoice
        fields = [
            "title",
            "rate",
            "client_name",
            "client_email",
        ]
        labels = {
            "client_name": "Client's name",
            "client_email": "Client's email",
        }
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "placeholder": "New Saas App...",
                    "class": "input input-bordered border-2 text-lg w-full",
                }
            ),
            "client_name": forms.TextInput(
                attrs={
                    "placeholder": "John Smith",
                    "class": "input input-bordered border-2 text-lg w-full",
                }
            ),
            "client_email": forms.EmailInput(
                attrs={
                    "placeholder": "john@company.com",
                    "class": "input input-bordered border-2 text-lg w-full",
                }
            ),
        }

    def clean_client_name(self):
        client_name = self.cleaned_data.get("client_name")
        if not all(x.isalpha() or x.isspace() for x in client_name):
            raise ValidationError("Only valid names allowed.")
        return client_name

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


class CreateInvoiceForm(InvoiceForm):
    contacts = forms.ChoiceField(
        required=False,
        label="Clients",
        widget=forms.Select(
            attrs={
                "class": "select select-bordered border-2 text-lg w-full",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["contacts"].choices = {
            (
                inv.client_stripe_customer_id,
                f"{inv.client_name} - {inv.client_email}",
            )
            for inv in Invoice.objects.filter(user=self.user)
        }
        self.fields["contacts"].choices.insert(0, ("", "Select a client"))
        # For the contacts logic
        self.fields["client_name"].required = False
        self.fields["client_email"].required = False

    class Meta(InvoiceForm.Meta):
        fields = InvoiceForm.Meta.fields + [
            "contacts",
        ]

    def clean(self):
        validated_data = super().clean()

        if validated_data.get("contacts") or (
            validated_data.get("client_email") and validated_data.get("client_name")
        ):
            # No missing client info
            pass
        else:
            raise ValidationError("A client needs be entered or selected from list")


class UpdateInvoiceForm(InvoiceForm):
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

    class Meta(InvoiceForm.Meta):
        fields = InvoiceForm.Meta.fields + [
            "total_budget",
        ]


def create_invoice_interval(superclass):
    class IntervalForm(superclass):
        def __init__(self, *args, **kwargs):
            super(IntervalForm, self).__init__(*args, **kwargs)
            self.fields["invoice_interval"].required = True

        class Meta(superclass.Meta):
            model = IntervalInvoice
            labels = {"rate": "Hourly rate", "invoice_interval": "Interval"}
            fields = superclass.Meta.fields + ["invoice_interval"]
            widgets = {
                **superclass.Meta.widgets,
                "invoice_interval": forms.Select(
                    attrs={
                        "class": "select select-bordered border-2 text-lg w-full",
                    }
                ),
            }

    return IntervalForm


CreateIntervalForm = create_invoice_interval(CreateInvoiceForm)
UpdateIntervalForm = create_invoice_interval(UpdateInvoiceForm)


def create_invoice_milestone(superclass):
    class MilestoneForm(superclass):
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

        def __init__(self, *args, **kwargs):
            super(MilestoneForm, self).__init__(*args, **kwargs)
            self.fields["milestone_total_steps"].required = True

        class Meta(superclass.Meta):
            model = MilestoneInvoice
            labels = {"rate": "Hourly rate"}
            fields = superclass.Meta.fields + ["milestone_total_steps"]

        def clean_milestone_total_steps(self):
            total_steps = self.cleaned_data.get("milestone_total_steps")
            if self.instance and self.instance.milestone_step:
                if total_steps < self.instance.milestone_step:
                    raise ValidationError(
                        "Cannot set milestone total steps to less than what is already completed"
                    )
            return total_steps

    return MilestoneForm


CreateMilestoneForm = create_invoice_milestone(CreateInvoiceForm)
UpdateMilestoneForm = create_invoice_milestone(UpdateInvoiceForm)


def create_invoice_weekly(superclass):
    class WeeklyForm(superclass):
        class Meta(superclass.Meta):
            model = WeeklyInvoice
            widgets = {
                **superclass.Meta.widgets,
                "rate": forms.NumberInput(
                    attrs={
                        "label": "Weekly rate",
                        "class": "input input-bordered border-2 text-lg w-full",
                        "max": 1_000_000,
                    }
                ),
            }

    return WeeklyForm


CreateWeeklyForm = create_invoice_weekly(CreateInvoiceForm)
UpdateWeeklyForm = create_invoice_weekly(UpdateInvoiceForm)


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
            != self.sent_invoice.invoice.client_email.lower()
        ):
            raise ValidationError(
                "Unable to process payment, please enter correct details."
            )

    def clean_first_name(self):
        cleaned_name = self.cleaned_data.get("first_name")
        if (
            cleaned_name.lower().strip()
            not in self.sent_invoice.invoice.client_name.lower()
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
        fields = ["phone_number_availability", "phone_number_repeat_sms"]


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
                "class": "input input-bordered border-2 bg-neutral text-xl "
                "w-full placeholder-gray-500 placeholder-opacity-7",
            }
        ),
    )
    full_name = forms.CharField(
        label="Full name",
        required=True,
        widget=forms.TextInput(
            attrs={
                "placeholder": "John Appleseed",
                "class": "input input-bordered border-2 bg-neutral text-xl "
                "w-full placeholder-gray-500 placeholder-opacity-7",
            }
        ),
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "*********",
                "type": "password",
                "class": "input input-bordered border-2 bg-neutral text-xl "
                "w-full placeholder-gray-500 placeholder-opacity-7",
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
                "class": "input input-bordered border-2 bg-neutral text-xl "
                "w-full placeholder-gray-500 placeholder-opacity-7 mb-2",
            }
        ),
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "*********",
                "type": "password",
                "class": "input input-bordered border-2 bg-neutral text-xl "
                "w-full placeholder-gray-500 placeholder-opacity-7",
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
        required=False,
        widget=forms.EmailInput(
            attrs={
                "class": "input input-bordered border-2 bg-neutral text-xl "
                "w-full placeholder-gray-500 placeholder-opacity-7",
                "placeholder": "Enter email here",
            }
        ),
    )
    phone_number = PhoneNumberField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "placeholder": "+13334445555",
                "class": "input input-bordered border-2 bg-neutral text-xl "
                "w-full placeholder-gray-500 placeholder-opacity-7",
            }
        ),
    )

    def clean(self):
        validate_data = super().clean()
        if not validate_data.get("email") and not validate_data.get("phone_number"):
            raise ValidationError(
                "Either an email or phone number is needed to send an invite."
            )
        return validate_data

    class Meta:
        fields = ["email", "phone_number"]


class UpdatePasswordForm(forms.Form):
    current_password = forms.CharField(
        label="Current Password",
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "*********",
                "type": "password",
                "class": "input input-bordered border-2 bg-neutral text-xl "
                "w-full placeholder-gray-500 placeholder-opacity-700/100",
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
                "class": "input input-bordered border-2 bg-neutral text-xl "
                "w-full placeholder-gray-500 placeholder-opacity-700/100",
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
