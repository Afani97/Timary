import datetime
import sys
import zoneinfo

import waffle
from django.conf import settings
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import Http404, HttpResponse, QueryDict
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from stripe.error import CardError, InvalidRequestError

from timary.forms import (
    InvoiceBrandingSettingsForm,
    LoginForm,
    ReferralInviteForm,
    SMSSettingsForm,
    UpdatePasswordForm,
)
from timary.models import Expenses, SentInvoice, User
from timary.services.email_service import EmailService
from timary.services.stripe_service import StripeService
from timary.services.twilio_service import TwilioClient
from timary.utils import generate_spreadsheet, get_users_localtime, show_alert_message


@login_required()
@require_http_methods(["GET"])
def settings_partial(request, setting):
    template = ""
    if setting == "sms":
        template = "partials/settings/preferences/_sms.html"
    if setting == "payment_method":
        template = "partials/settings/account/_payment_method.html"
    if setting == "referral":
        template = "partials/settings/account/_referrals.html"
    if setting == "password":
        template = "partials/settings/account/_password.html"
    if setting == "accounting":
        template = "partials/settings/bookkeeping/_accounting.html"
    if setting == "tax_center":
        template = "partials/settings/bookkeeping/_tax_center.html"
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
        except (InvalidRequestError, CardError) as e:
            if not settings.DEBUG:
                print(
                    f"Error updating payment method: user.id={request.user.id}, error={str(e)}",
                    file=sys.stderr,
                )
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
                "todays_date": get_users_localtime(request.user),
                "yesterday_date": get_users_localtime(request.user)
                - timezone.timedelta(days=1),
            }
        )
        return render(request, "invoices/invoice_branding.html", context)

    else:
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


@login_required
@require_http_methods(["GET"])
def update_accounting_integrations(request):
    context = {
        "profile": request.user,
        "settings": request.user.settings,
    }
    return render(
        request,
        "partials/settings/bookkeeping/_edit_accounting.html",
        context,
    )


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
        subscription_cancelled = StripeService.cancel_subscription(request.user)
        response = render(request, "partials/settings/account/_add_subscription.html")
        if "from_delete_account" in request.GET:
            # Canceling the subscription from the account delete page
            response["HX-Redirect"] = "/profile/"
        if subscription_cancelled:
            show_alert_message(
                response,
                "warning",
                "We're sorry to see you go. Note, no more invoices or accounting service "
                "will be updated until you re-subscribe.",
                persist=True,
            )
        else:
            show_alert_message(
                response,
                "warning",
                "Error while cancelling your subscription, please try again.",
                persist=True,
            )
        return response
    elif action.lower() == "add":
        subscription_created = StripeService.readd_subscription(request.user)
        response = render(
            request, "partials/settings/account/_cancel_subscription.html"
        )
        if subscription_created:
            show_alert_message(
                response,
                "success",
                "Hooray! We're happy you're back! "
                "Please let us know if you have any questions. Other than that, welcome!",
                persist=True,
            )
        else:
            show_alert_message(
                response,
                "error",
                "Error while re-adding the subscription! Try updating the payment method then resubscribe.",
                persist=True,
            )
        return response
    return Http404


@login_required
@require_http_methods(["GET"])
def view_tax_center(request):
    local_tz = zoneinfo.ZoneInfo(request.user.timezone)
    tax_years = [
        "2024"
    ]  # Add another year for new tax season to calculate previous year
    tax_summary = []
    for tax_year in tax_years:
        if not waffle.switch_is_active(f"can_view_{tax_year}"):
            continue
        previous_year_range = (
            datetime.datetime(year=int(tax_year) - 1, month=1, day=1, tzinfo=local_tz),
            datetime.datetime(year=int(tax_year), month=1, day=1, tzinfo=local_tz),
        )
        gross_profit = (
            SentInvoice.objects.filter(
                user=request.user,
                date_paid__range=previous_year_range,
                paid_status=SentInvoice.PaidStatus.PAID,
            ).aggregate(gross_profit=Sum("total_price"))["gross_profit"]
            or 0
        )
        total_expenses = (
            Expenses.objects.filter(
                invoice__user=request.user, date_tracked__range=previous_year_range
            ).aggregate(total_expenses=Sum("cost"))["total_expenses"]
            or 0
        )
        tax_summary.append(
            {
                "tax_year": tax_year,
                "income_year": int(tax_year) - 1,
                "gross_profit": gross_profit,
                "total_expenses": total_expenses,
            }
        )
    context = {"tax_summary": tax_summary}

    return render(request, "taxes/_tax_summary.html", context)


@login_required
@require_http_methods(["GET"])
def audit(request):
    year = request.GET.get("year")
    csv_filename = "timary_audit_activity.csv"
    year_date_range = None
    if year:
        csv_filename = f"timary_audit_activity_{year}.csv"
        tz_info = zoneinfo.ZoneInfo(request.user.timezone)
        year_date_range = (
            datetime.datetime(year=int(year), month=1, day=1, tzinfo=tz_info),
            datetime.datetime(year=int(year) + 1, month=1, day=1, tzinfo=tz_info),
        )

    response = HttpResponse(
        content_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={csv_filename}"},
    )
    return generate_spreadsheet(response, request.user, year_date_range)


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
                f"{reverse('timary:register')}?referrer_id={request.user.referral_id}"
            )
            if form.cleaned_data.get("email", None):
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

            if form.cleaned_data.get("phone_number", None):
                TwilioClient.invite_user(
                    form.cleaned_data.get("phone_number"),
                    f"""
Hello! You've been invited by {request.user.first_name.capitalize()} to give Timary a try!

Please follow this link {referrer_email_link} to get started today.

tldr for Timary.
We are a time tracking, invoicing, bookkeeping syncing service to help streamline your business.

Regards,
Timary Team
                    """,
                )
            context["success"] = "Invite sent! Send another"
        else:
            context["error"] = "Unable to send invite, try again!"
    return render(request, "partials/settings/account/_invite_referral.html", context)
