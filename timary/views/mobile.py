from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    parser_classes,
    permission_classes,
    renderer_classes,
)
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework_xml.renderers import XMLRenderer

from timary.forms import DailyHoursForm, InvoiceForm, UserForm
from timary.models import DailyHoursInput, Invoice
from timary.utils import render_xml
from timary.views import get_hours_tracked


def mobile_index(request):
    return render_xml(request, "index.xml")


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def mobile_hours(request):
    hours = DailyHoursInput.all_hours.current_month(request.user)
    show_repeat_option = request.user.can_repeat_previous_hours_logged(hours)

    context = {
        "new_hour_form": DailyHoursForm(user=request.user),
        "hours": hours,
        "show_repeat": show_repeat_option,
    }
    context.update(get_hours_tracked(request.user))
    t = "hours/hours.xml"
    if "partial" in request.query_params:
        t = "hours/_hours.xml"
    return render_xml(request, t, context)


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@renderer_classes([XMLRenderer])
@parser_classes([FormParser, MultiPartParser])
def mobile_new_hours(request):
    if request.method == "POST":
        hours = DailyHoursForm(request.data)
        if hours.is_valid():
            hours.save()
            return render_xml(
                request, "new-hours/new_hours_form.xml", {"success": True}
            )
        else:
            return render_xml(
                request, "new-hours/new_hours_form.xml", {"errors": hours.errors}
            )
    else:
        return render_xml(
            request,
            "new-hours/new_hours.xml",
            {"user_invoices": request.user.get_invoices},
        )


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def mobile_view_hours(request, hours_id):
    hour = get_object_or_404(DailyHoursInput, id=hours_id)
    if request.user != hour.invoice.user:
        raise Http404
    return render_xml(request, "hours/_hour.xml", {"hour": hour})


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def mobile_hour_stats(request):
    return render_xml(request, "hours/_stats.xml", get_hours_tracked(request.user))


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@renderer_classes([XMLRenderer])
@parser_classes([FormParser, MultiPartParser])
def mobile_edit_hours(request, hours_id):
    hour = get_object_or_404(DailyHoursInput, id=hours_id)
    if request.user != hour.invoice.user:
        raise Http404
    if request.method == "POST":
        hours = DailyHoursForm(request.data, instance=hour)
        if hours.is_valid():
            hours.save()
            context = {"hour": hour, "success": True}
        else:
            context = {"hour": hour, "errors": hours.errors}
        return render_xml(request, "edit-hours/edit_hours_form.xml", context)
    else:
        return render_xml(
            request,
            "edit-hours/edit_hours.xml",
            {"hour": hour, "user_invoices": request.user.get_invoices},
        )


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def mobile_delete_hours(request, hours_id):
    hours = get_object_or_404(DailyHoursInput, id=hours_id)
    if request.user != hours.invoice.user:
        raise Http404
    hours.delete()
    return render_xml(request, "empty.xml")


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def mobile_invoices(request):
    invoices = request.user.get_invoices.order_by("title")
    t = "invoices/invoices.xml"
    if "partial" in request.query_params:
        t = "invoices/_invoices.xml"
    return render_xml(request, t, {"invoices": invoices})


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def mobile_view_invoice(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    if request.user != invoice.user:
        raise Http404
    return render_xml(request, "invoices/_invoice.xml", {"invoice": invoice})


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@renderer_classes([XMLRenderer])
@parser_classes([FormParser, MultiPartParser])
def mobile_new_invoices(request):
    invoice_form = InvoiceForm(None)
    if request.method == "POST":
        request_data = request.POST.copy()
        if int(request_data.get("invoice_type")) == Invoice.InvoiceType.WEEKLY:
            request_data.update({"invoice_rate": request_data["weekly_rate"]})
        else:
            request_data.update({"invoice_rate": request_data["hourly_rate"]})
        invoice_form = InvoiceForm(request_data)
        if invoice_form.is_valid():
            # Hide create button if unable to create more
            prev_invoice_count = request.user.get_invoices.count()
            invoice = invoice_form.save(commit=False)
            invoice.user = request.user
            invoice.calculate_next_date()
            invoice.save()
            invoice.sync_customer()
            context = {"success": True}
        else:
            context = {"errors": invoice_form.errors}
        return render_xml(
            request,
            "new-invoices/new_invoice_form.xml",
            context,
        )
    else:
        return render_xml(
            request,
            "new-invoices/new_invoice.xml",
            {"invoice_form": invoice_form},
        )


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@renderer_classes([XMLRenderer])
@parser_classes([FormParser, MultiPartParser])
def mobile_edit_invoice(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    if request.user != invoice.user:
        raise Http404
    if request.method == "POST":
        request_data = request.POST.copy()
        if invoice.invoice_type == Invoice.InvoiceType.WEEKLY:
            request_data.update({"invoice_rate": request_data["weekly_rate"]})
        invoice_form = InvoiceForm(request_data, instance=invoice, user=request.user)
        if invoice_form.is_valid():
            invoice = invoice_form.save()
            if invoice.next_date:
                invoice.calculate_next_date(update_last=False)
            context = {"invoice": invoice, "success": True}
        else:
            context = {"invoice": invoice, "errors": invoice_form.errors}
        return render_xml(
            request,
            "edit-invoice/edit_invoice_form.xml",
            context,
        )
    else:
        return render_xml(
            request, "edit-invoice/edit_invoice.xml", {"invoice": invoice}
        )


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def mobile_profile(request):
    t = "profile/profile.xml"
    if "partial" in request.query_params:
        t = "profile/_profile.xml"
    return render_xml(request, t, {"profile": request.user})


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@renderer_classes([XMLRenderer])
@parser_classes([FormParser, MultiPartParser])
def mobile_edit_profile(request):
    if request.method == "POST":
        profile = UserForm(request.data, instance=request.user)
        if profile.is_valid():
            profile.save()
            context = {"profile": request.user, "success": True}
        else:
            context = {"profile": request.user, "errors": profile.errors}
        return render_xml(request, "edit-profile/edit_profile_form.xml", context)
    else:
        return render_xml(
            request, "edit-profile/edit_profile.xml", {"profile": request.user}
        )
