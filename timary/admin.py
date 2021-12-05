from django import forms
from django.contrib import admin, messages
from django.core.mail import send_mail
from django.template.response import TemplateResponse
from django.urls import path

from timary.models import DailyHoursInput, Invoice, User

# Register your models here.
admin.site.register(User)
admin.site.register(Invoice)
admin.site.register(DailyHoursInput)


class SendEmailForm(forms.Form):
    subject = forms.CharField(max_length=300)
    message = forms.CharField(max_length=2000, widget=forms.Textarea)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["message"].widget.attrs["rows"] = 8
        self.fields["message"].widget.attrs["cols"] = 15
        self.fields["message"].widget.attrs["textarea"] = True


def send_emails(subject, message):
    send_mail(
        subject,
        message,
        None,
        recipient_list=User.objects.all().values_list("email", flat=True),
        fail_silently=False,
    )


class TimaryAdminSite(admin.AdminSite):
    index_template = "admin/custom_index.html"

    def custom_page(self, request):
        context = {
            "text": "Hello Admin",
            "page_name": "Custom Page",
            "app_list": self.get_app_list(request),
            **self.each_context(request),
        }
        return TemplateResponse(request, "admin/custom_page.html", context)

    def send_email(self, request):
        context = {
            "text": "Send Email",
            "form": SendEmailForm(),
            "page_name": "Send Email",
            "app_list": self.get_app_list(request),
            **self.each_context(request),
        }
        if request.method == "POST":
            form = SendEmailForm(request.POST)
            if form.is_valid():
                subject = form.cleaned_data.get("subject")
                message = form.cleaned_data.get("message")
                send_emails(subject, message)
                messages.add_message(
                    request, messages.INFO, "Successfully sent out emails."
                )
        return TemplateResponse(request, "admin/send_email.html", context)

    def get_urls(self):
        return [
            path(
                "custom_page/",
                self.admin_view(self.custom_page),
                name="custom_page",
            ),
            path(
                "send_email/",
                self.admin_view(self.send_email),
                name="send_email",
            ),
        ] + super().get_urls()
