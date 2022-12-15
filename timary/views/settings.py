import datetime
from tempfile import NamedTemporaryFile

from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import Http404, HttpResponse, QueryDict
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from openpyxl import Workbook
from openpyxl.worksheet.table import Table, TableStyleInfo
from stripe.error import InvalidRequestError

from timary.forms import (
    InvoiceBrandingSettingsForm,
    LoginForm,
    ReferralInviteForm,
    SMSSettingsForm,
    UpdatePasswordForm,
)
from timary.models import SentInvoice, User
from timary.services.email_service import EmailService
from timary.services.stripe_service import StripeService
from timary.utils import show_alert_message


@login_required()
@require_http_methods(["GET"])
def settings_partial(request, setting):
    template = ""
    if setting == "sms":
        template = "partials/settings/preferences/_sms.html"
    if setting == "payment_method":
        template = "partials/settings/account/_payment_method.html"
    if setting == "accounting":
        template = "partials/settings/account/_accounting.html"
    if setting == "referral":
        template = "partials/settings/account/_referrals.html"
    if setting == "password":
        template = "partials/settings/account/_password.html"
    return render(
        request,
        template,
        {"profile": request.user, "settings": request.user.settings},
    )


@login_required()
@require_http_methods(["GET", "PUT"])
def update_sms_settings(request):
    context = {
        "settings_form": SMSSettingsForm(instance=request.user),
        "settings": request.user.settings,
    }
    if request.method == "GET":
        return render(
            request, "partials/settings/preferences/_edit_sms.html", context=context
        )

    elif request.method == "PUT":
        put_params = dict(QueryDict(request.body))
        user_settings_form = SMSSettingsForm(put_params, instance=request.user)
        if user_settings_form.is_valid():
            user_settings_form.save()
            response = render(
                request,
                "partials/settings/preferences/_sms.html",
                {"settings": request.user.settings},
            )
            show_alert_message(
                response,
                "success",
                "Settings updated",
            )
            return response
        else:
            context["settings_form"] = user_settings_form
            return render(
                request, "partials/settings/preferences/_edit_sms.html", context
            )

    else:
        raise Http404()


@login_required()
@require_http_methods(["GET", "POST"])
def update_payment_method_settings(request):
    context = {
        "client_secret": StripeService.create_payment_intent(),
        "stripe_public_key": StripeService.stripe_public_api_key,
        "stripe_card_element_ui": StripeService.frontend_ui(),
    }
    stripe_errors = {
        **context,
        "stripe_errors": {"errors": "Error updating payment method, please try again."},
    }

    if request.method == "POST":
        if "first_token" not in request.POST or "second_token" not in request.POST:
            return render(
                request,
                "partials/settings/account/_edit_payment_method.html",
                stripe_errors,
            )
        try:
            success = StripeService.update_payment_method(
                request.user,
                request.POST.get("first_token"),
                request.POST.get("second_token"),
            )
        except InvalidRequestError:
            return render(
                request,
                "partials/settings/account/_edit_payment_method.html",
                stripe_errors,
            )
        if success:
            response = render(
                request,
                "partials/settings/account/_payment_method.html",
                {"settings": request.user.settings},
            )
            show_alert_message(
                response,
                "success",
                "Successfully updated debit card.",
            )
            return response
        else:
            return render(
                request,
                "partials/settings/account/_edit_payment_method.html",
                stripe_errors,
            )

    return render(
        request, "partials/settings/account/_edit_payment_method.html", context
    )


@login_required()
@require_http_methods(["GET", "POST"])
def update_invoice_branding(request):
    user: User = request.user
    invoice_branding_form = InvoiceBrandingSettingsForm(
        initial=user.invoice_branding, data=request.POST or None
    )
    context = {
        "settings_form": invoice_branding_form,
        "invoice_branding_config": user.invoice_branding_properties(),
    }
    if request.method == "GET":
        context.update(
            {
                "todays_date": datetime.date.today(),
                "yesterday_date": datetime.date.today() - datetime.timedelta(days=1),
            }
        )
        return render(request, "invoices/invoice_branding.html", context)

    elif request.method == "POST":

        if invoice_branding_form.is_valid():
            for k, v in invoice_branding_form.cleaned_data.items():
                user.invoice_branding[k] = v
            user.save()
            response = render(request, "invoices/invoice_branding.html", context)
            show_alert_message(
                response,
                "success",
                "Invoice branding updated",
            )
            return response
        else:
            response = render(request, "invoices/invoice_branding.html", context)
            show_alert_message(
                response,
                "error",
                "Unable to update Invoice branding",
            )
            return response

    else:
        raise Http404()


@login_required
@require_http_methods(["GET"])
def update_accounting_integrations(request):
    context = {
        "profile": request.user,
        "settings": request.user.settings,
    }
    return render(request, "partials/settings/account/_edit_accounting.html", context)


@login_required()
@require_http_methods(["GET", "PUT"])
def update_user_password(request):
    context = {
        "password_form": UpdatePasswordForm(),
    }
    if request.method == "GET":
        return render(
            request, "partials/settings/account/_edit_password.html", context=context
        )

    elif request.method == "PUT":
        put_params = QueryDict(request.body)
        password_form = UpdatePasswordForm(put_params, user=request.user)
        if password_form.is_valid():
            new_password = password_form.cleaned_data.get("new_password")
            request.user.set_password(new_password)
            request.user.save()
            response = render(request, "auth/login.html", {"form": LoginForm()})
            response["HX-Redirect"] = "/login/"
            logout(request)
            return response
        else:
            context["password_form"] = UpdatePasswordForm()
            response = render(
                request, "partials/settings/account/_edit_password.html", context
            )
            show_alert_message(
                response, "error", "Unable to update, please try again.", persist=True
            )
            return response

    else:
        raise Http404()


@login_required()
@require_http_methods(["GET"])
def update_subscription(request):
    action = request.GET.get("action")
    if action.lower() == "cancel":
        StripeService.cancel_subscription(request.user)
        response = render(request, "partials/settings/account/_add_subscription.html")
        show_alert_message(
            response,
            "warning",
            "We're sorry to see you go. Note, no more invoices or accounting service "
            "will be updated until you re-subscribe.",
            persist=True,
        )
        return response
    elif action.lower() == "add":
        StripeService.readd_subscription(request.user)
        response = render(
            request, "partials/settings/account/_cancel_subscription.html"
        )
        show_alert_message(
            response,
            "success",
            "Hooray! We're happy you're back! Please let us know if you have any questions. Other than that, welcome!",
            persist=True,
        )
        return response
    return Http404


@login_required
@require_http_methods(["GET"])
def audit(request):
    wb = Workbook()
    ws = wb.active
    ws.title = "Your Timary audit activity"

    sent_invoices = SentInvoice.objects.filter(user=request.user).order_by("date_sent")

    # add column headings. NB. these must be strings
    ws.append(
        [
            "Date Sent",
            "Invoice #",
            "Invoice Title",
            "User #",
            "Hours Start Date",
            "Hours End Date",
            "Total Hours",
            "Total Price",
            "Paid Status",
        ]
    )

    # add sent invoice data per row
    for sent_invoice in sent_invoices:
        total_hours = sent_invoice.invoice.hours_tracked.filter(
            date_tracked__range=[
                sent_invoice.hours_start_date,
                sent_invoice.hours_end_date,
            ]
        ).aggregate(hours=Sum("hours"))
        ws.append(
            [
                sent_invoice.date_sent.strftime("%Y-%m-%d"),
                str(sent_invoice.invoice.id),
                sent_invoice.invoice.title,
                str(sent_invoice.user.id),
                sent_invoice.hours_start_date.strftime("%Y-%m-%d"),
                sent_invoice.hours_end_date.strftime("%Y-%m-%d"),
                total_hours["hours"],
                str(sent_invoice.total_price),
                sent_invoice.get_paid_status_display(),
            ]
        )

    tab = Table(displayName="Table1", ref=f"A1:G{len(sent_invoices) + 1}")

    style = TableStyleInfo(
        name="TableStyleMedium9",
        showFirstColumn=False,
        showLastColumn=False,
        showRowStripes=True,
        showColumnStripes=True,
    )
    tab.tableStyleInfo = style
    ws.add_table(tab)

    # save to temp file for Django to send in response
    with NamedTemporaryFile() as tmp:
        wb.save(tmp.name)
        tmp.seek(0)
        stream = tmp.read()

    response = HttpResponse(
        content=stream,
        content_type="application/ms-excel",
    )
    response["Content-Disposition"] = "attachment; filename=Timary-Audit-Activity.xlsx"
    return response


@login_required()
@require_http_methods(["GET", "POST"])
def invite_new_user(request):
    context = {
        "profile": request.user,
        "settings": request.user.settings,
        "invite_form": ReferralInviteForm(),
    }
    if request.method == "POST":
        form = ReferralInviteForm(request.POST)
        if form.is_valid():
            referrer_email_link = request.build_absolute_uri(
                f"{reverse('timary:register')}?referrer_id={request.user.referrer_id}"
            )
            EmailService.send_plain(
                "You've been invited to try Timary!",
                f"""
Hello!

{request.user.first_name} has invited you to give Timary a try.

They believe Timary might be a good fit for your needs.

What is Timary? Timary is a service helping folks get paid easily when they are completing their projects.

We help with time tracking, invoicing, and syncing to your accounting service so tax season is a breeze.

If you'd like to read more about us, visit: https://www.usetimary.com


To sign up with {request.user.first_name}'s referral code, click on this link to get you registered with Timary:
{referrer_email_link}


I hope Timary is right for you,

Aristotel F
Timary LLC

                """,
                form.cleaned_data.get("email"),
            )
            context["success"] = "Invite sent! Send another"
        else:
            context["error"] = "Unable to send invite, try again!"
    return render(request, "partials/settings/account/_invite_referral.html", context)
