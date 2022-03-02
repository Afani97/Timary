from tempfile import NamedTemporaryFile

from crispy_forms.utils import render_crispy_form
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import HttpResponse, QueryDict
from django.shortcuts import render
from django.template.context_processors import csrf
from django.views.decorators.http import require_http_methods
from openpyxl import Workbook
from openpyxl.worksheet.table import Table, TableStyleInfo

from timary.forms import SettingsForm, UserForm
from timary.models import SentInvoice
from timary.services.stripe_service import StripeService


@login_required()
@require_http_methods(["GET"])
def user_profile(request):
    context = {
        "profile": request.user,
        "settings": request.user.settings,
        "sent_invoices": request.user.sent_invoices.order_by("-date_sent"),
    }
    return render(request, "timary/profile.html", context)


@login_required()
@require_http_methods(["GET"])
def profile_partial(request):
    return render(request, "partials/_profile.html", {"profile": request.user})


@login_required()
@require_http_methods(["GET"])
def edit_user_profile(request):
    profile_form = UserForm(instance=request.user, is_mobile=request.is_mobile)
    ctx = {}
    ctx.update(csrf(request))
    html_form = render_crispy_form(profile_form, context=ctx)
    return HttpResponse(html_form)


@login_required()
@require_http_methods(["PUT"])
def update_user_profile(request):
    current_membership_tier = request.user.membership_tier
    put_params = QueryDict(request.body)
    user_form = UserForm(put_params, instance=request.user, is_mobile=request.is_mobile)
    if user_form.is_valid():
        user = user_form.save()
        if user_form.cleaned_data.get("membership_tier") != current_membership_tier:
            StripeService.create_subscription(user, delete_current=True)
        return render(request, "partials/_profile.html", {"user": user})
    ctx = {}
    ctx.update(csrf(request))
    html_form = render_crispy_form(user_form, context=ctx)
    return HttpResponse(html_form)


@login_required()
@require_http_methods(["GET"])
def settings_partial(request):
    return render(
        request, "partials/_settings.html", {"settings": request.user.settings}
    )


@login_required()
@require_http_methods(["GET", "PUT"])
def update_user_settings(request):
    user_settings_form = SettingsForm(instance=request.user)
    if request.method == "PUT":
        put_params = QueryDict(request.body)
        user_settings_form = SettingsForm(put_params, instance=request.user)
        if user_settings_form.is_valid():
            user_settings_form.save()
            return render(
                request, "partials/_settings.html", {"settings": request.user.settings}
            )
    context = {
        "form": user_settings_form,
    }
    return render(request, "partials/_settings_form.html", context)


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
