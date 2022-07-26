import datetime
from tempfile import NamedTemporaryFile

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import Http404, HttpResponse, QueryDict
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from openpyxl import Workbook
from openpyxl.worksheet.table import Table, TableStyleInfo
from stripe.error import InvalidRequestError

from timary.forms import (
    InvoiceBrandingSettingsForm,
    MembershipTierSettingsForm,
    SMSSettingsForm,
)
from timary.models import SentInvoice, User
from timary.services.stripe_service import StripeService
from timary.utils import show_alert_message


@login_required()
@require_http_methods(["GET"])
def settings_partial(request, setting):
    template = ""
    if setting == "sms":
        template = "partials/settings/_sms.html"
    if setting == "membership":
        template = "partials/settings/_membership.html"
    if setting == "payment_method":
        template = "partials/settings/_payment_method.html"
    if setting == "accounting":
        template = "partials/settings/_accounting.html"
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
        return render(request, "partials/settings/_edit_sms.html", context=context)

    elif request.method == "PUT":
        put_params = dict(QueryDict(request.body))
        user_settings_form = SMSSettingsForm(put_params, instance=request.user)
        if user_settings_form.is_valid():
            user_settings_form.save()
            response = render(
                request,
                "partials/settings/_sms.html",
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
            return render(request, "partials/settings/_edit_sms.html", context)

    else:
        raise Http404()


@login_required()
@require_http_methods(["GET", "PUT"])
def update_membership_settings(request):
    context = {
        "settings_form": MembershipTierSettingsForm(instance=request.user),
        "settings": request.user.settings,
        "current_plan": request.user.get_membership_tier_display().title(),
    }
    if request.method == "GET":
        return render(request, "partials/settings/_edit_membership.html", context)

    elif request.method == "PUT":
        put_params = dict(QueryDict(request.body))
        user_settings_form = MembershipTierSettingsForm(
            put_params, instance=request.user
        )
        current_membership_tier = request.user.membership_tier
        put_params["membership_tier"] = str(
            User.MembershipTier[put_params["membership_tier"][0]].value
        )
        if user_settings_form.is_valid():
            user_settings_form.save()
            if current_membership_tier and user_settings_form.cleaned_data.get(
                "membership_tier"
            ):
                StripeService.create_subscription(request.user, delete_current=True)
            response = render(
                request,
                "partials/settings/_membership.html",
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
            return render(request, "partials/settings/_edit_membership.html", context)
    else:
        raise Http404()


@login_required()
@require_http_methods(["GET", "POST"])
def update_payment_method_settings(request):
    context = {
        "client_secret": StripeService.create_payment_intent(),
        "stripe_public_key": StripeService.stripe_public_api_key,
    }
    if request.method == "GET":
        return render(request, "partials/settings/_edit_payment_method.html", context)

    elif request.method == "POST":
        request_data = request.POST.copy()
        try:
            success = StripeService.update_payment_method(
                request.user,
                request_data.pop("first_token")[0],
                request_data.pop("second_token")[0],
            )
        except InvalidRequestError:
            messages.error(
                request, "Error updating payment method, Stripe requires a debit card."
            )
            return redirect(reverse("timary:user_profile"))
        if success:
            messages.info(request, "Successfully updated debit card.")
        else:
            messages.error(
                request, "Error updating payment method, Stripe requires a debit card."
            )
        return redirect(reverse("timary:user_profile"))

    else:
        raise Http404()


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

    elif request.method == "POST" and request.user.can_customize_invoice:

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
    return render(request, "partials/settings/_update_accounting.html", context)


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
