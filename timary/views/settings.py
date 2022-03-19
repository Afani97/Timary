from tempfile import NamedTemporaryFile

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import Http404, HttpResponse, QueryDict
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from openpyxl import Workbook
from openpyxl.worksheet.table import Table, TableStyleInfo

from timary.forms import MembershipTierSettingsForm, SMSSettingsForm
from timary.models import SentInvoice, User
from timary.services.stripe_service import StripeService


@login_required()
@require_http_methods(["GET"])
def settings_partial(request, setting):
    template = ""
    if setting == "sms":
        template = "partials/settings/_sms.html"
    if setting == "membership":
        template = "partials/settings/_membership.html"
    return render(
        request,
        template,
        {"settings": request.user.settings},
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
            return render(
                request,
                "partials/settings/_sms.html",
                {"settings": request.user.settings},
            )
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
            if (
                current_membership_tier
                and user_settings_form.cleaned_data.get("membership_tier")
                != current_membership_tier
            ):
                StripeService.create_subscription(request.user, delete_current=True)
            return render(
                request,
                "partials/settings/_membership.html",
                {"settings": request.user.settings},
            )
        else:
            context["settings_form"] = user_settings_form
            return render(request, "partials/settings/_edit_membership.html", context)
    else:
        raise Http404()


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
