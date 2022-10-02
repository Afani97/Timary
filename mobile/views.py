import datetime

from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
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

from mobile.utils import render_xml, render_xml_frag
from timary.forms import DailyHoursForm, InvoiceForm, QuestionsForm, UserForm
from timary.models import DailyHoursInput, Invoice, SentInvoice
from timary.services.email_service import EmailService
from timary.views import get_hours_tracked, resend_invoice_email


class CustomAuthToken(ObtainAuthToken):
    parser_classes = (
        FormParser,
        MultiPartParser,
    )
    renderer_classes = (XMLRenderer,)

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            user = serializer.validated_data["user"]
            token, created = Token.objects.get_or_create(user=user)
            return render(
                request,
                "mobile/_login_form.xml",
                context={"success": True, "token": token},
                content_type="application/xml",
            )
        else:
            return render(
                request,
                "mobile/_login_form.xml",
                context={"errors": ["Unable to login with credentials"]},
                content_type="application/xml",
            )


def index(request):
    return render_xml(request, "index.xml")


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_hours(request):
    hours_list = DailyHoursInput.all_hours.current_month(request.user)
    show_repeat_option = request.user.can_repeat_previous_hours_logged(hours_list)

    context = {
        "new_hour_form": DailyHoursForm(user=request.user),
        "hours": hours_list,
        "show_repeat": show_repeat_option,
    }
    context.update(get_hours_tracked(request.user))
    if "partial" in request.query_params:
        return render_xml_frag("hours/hours.xml", "hours", context)
    else:
        return render_xml(request, "hours/hours.xml", context)


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@renderer_classes([XMLRenderer])
@parser_classes([FormParser, MultiPartParser])
def new_hours(request):
    context = {"user_invoices": request.user.get_invoices}
    if request.method == "POST":
        hours_form = DailyHoursForm(request.data, user=request.user)
        if hours_form.is_valid():
            hours_form.save()
            context.update(
                {
                    "success": True,
                    "toast_message": "New hours added!",
                    "toast_type": "success",
                }
            )
        else:
            context.update(
                {
                    "errors": hours_form.errors,
                    "toast_message": "Error creating hours",
                    "toast_type": "error",
                }
            )
        return render_xml_frag("new_hours.xml", "new-hours-form", context)
    else:
        return render_xml(
            request,
            "new_hours.xml",
            context,
        )


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def view_hours(request, hours_id):
    hour = get_object_or_404(DailyHoursInput, id=hours_id)
    if request.user != hour.invoice.user:
        raise Http404
    return render_xml(request, "hours/_hour.xml", {"hour": hour})


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def hour_stats(request):
    return render_xml_frag(
        "hours/hours.xml", "hour-stats", get_hours_tracked(request.user)
    )


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@renderer_classes([XMLRenderer])
@parser_classes([FormParser, MultiPartParser])
def edit_hours(request, hours_id):
    hour = get_object_or_404(DailyHoursInput, id=hours_id)
    if request.user != hour.invoice.user:
        raise Http404
    context = {"hour": hour, "user_invoices": request.user.get_invoices}
    if request.method == "POST":
        hours_form = DailyHoursForm(request.data, instance=hour)
        if hours_form.is_valid():
            hours_form.save()
            context.update(
                {
                    "success": True,
                    "toast_message": "Hours updated!",
                    "toast_type": "success",
                }
            )
        else:
            context.update(
                {
                    "errors": hours_form.errors,
                    "toast_message": "Error updating hours",
                    "toast_type": "error",
                }
            )
        return render_xml_frag("edit_hours.xml", "edit-hours-form", context)
    else:
        return render_xml(
            request,
            "edit_hours.xml",
            context,
        )


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def delete_hours(request, hours_id):
    hour = get_object_or_404(DailyHoursInput, id=hours_id)
    if request.user != hour.invoice.user:
        raise Http404
    hour.delete()
    return render_xml(
        request, "empty.xml", {"toast_message": "Hours deleted!", "toast_type": "info"}
    )


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_invoices(request):
    invoices_list = request.user.get_invoices.order_by("title")
    t = "invoices/invoices.xml"
    c = {"invoices": invoices_list}
    if "partial" in request.query_params:
        return render_xml_frag(t, "invoices", c)
    else:
        return render_xml(request, t, c)


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def view_invoice(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    if request.user != invoice.user:
        raise Http404
    c = {"invoice": invoice}
    t = "invoices/_invoice.xml"
    if "detail_view" in request.query_params:
        t = "invoices/_invoice_detail.xml"
        c["invoice_detail_html"] = render_to_string(
            "mobile/invoices/_invoice_detail.html", c
        )
    return render_xml(request, t, c)


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@renderer_classes([XMLRenderer])
@parser_classes([FormParser, MultiPartParser])
def new_invoices(request):
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
            # prev_invoice_count = request.user.get_invoices.count()
            invoice = invoice_form.save(commit=False)
            invoice.user = request.user
            invoice.calculate_next_date()
            invoice.save()
            invoice.sync_customer()
            context = {
                "success": True,
                "toast_message": "New invoice added!",
                "toast_type": "success",
            }
        else:
            context = {
                "errors": invoice_form.errors,
                "toast_message": "Error creating invoice",
                "toast_type": "error",
            }
        return render_xml_frag(
            "new_invoice.xml",
            "new-invoice-form",
            context,
        )
    else:
        return render_xml(
            request,
            "new_invoice.xml",
            {"invoice_form": invoice_form},
        )


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@renderer_classes([XMLRenderer])
@parser_classes([FormParser, MultiPartParser])
def edit_invoice(request, invoice_id):
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
            context = {
                "invoice": invoice,
                "success": True,
                "toast_message": "Invoice updated!",
                "toast_type": "success",
            }
        else:
            context = {
                "invoice": invoice,
                "errors": invoice_form.errors,
                "toast_message": "Error updating this invoice",
                "toast_type": "error",
            }
        return render_xml_frag(
            "edit_invoice.xml",
            "edit-invoice-form",
            context,
        )
    else:
        return render_xml(request, "edit_invoice.xml", {"invoice": invoice})


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@renderer_classes([XMLRenderer])
@parser_classes([FormParser, MultiPartParser])
def get_timer(request):
    invoices = request.user.get_invoices.order_by("title")
    c = {"invoices": invoices}
    if request.method == "POST":
        request_data = request.POST.copy()
        request_data["date_tracked"] = datetime.datetime.today()
        hours_form = DailyHoursForm(request_data, user=request.user)
        if hours_form.is_valid():
            hours_form.save()
            c.update(
                {
                    "success": True,
                    "toast_message": "New hours added!",
                    "toast_type": "success",
                }
            )
        else:
            c.update(
                {
                    "errors": hours_form.errors,
                }
            )
        return render_xml_frag("timer.xml", "timer-form", c)
    else:
        return render_xml(request, "timer.xml", c)


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_sent_invoices(request):
    sent_invoices_list = request.user.sent_invoices.order_by("-date_sent")
    t = "sent-invoices/sent_invoices.xml"
    c = {"sent_invoices": sent_invoices_list}
    if "partial" in request.query_params:
        return render_xml_frag(t, "sent-invoices", c)
    else:
        return render_xml(request, t, c)


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def view_sent_invoice(request, sent_invoice_id):
    sent_invoice = get_object_or_404(SentInvoice, id=sent_invoice_id)
    if request.user != sent_invoice.user:
        raise Http404
    return render_xml(
        request, "sent-invoices/_sent_invoice.xml", {"sent_invoice": sent_invoice}
    )


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def resend_invoice(request, sent_invoice_id):
    sent_invoice = get_object_or_404(SentInvoice, id=sent_invoice_id)
    if request.user != sent_invoice.user:
        raise Http404
    _ = resend_invoice_email(request, sent_invoice_id)
    return render_xml(
        request,
        "sent-invoices/_sent_invoice.xml",
        {
            "sent_invoice": sent_invoice,
            "success": True,
            "toast_message": "Invoice resent!",
            "toast_type": "success",
        },
    )


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_profile(request):
    c = {"profile": request.user}
    if "partial" in request.query_params:
        return render_xml_frag("profile.xml", "profile", c)
    else:
        return render_xml(request, "profile.xml", c)


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@renderer_classes([XMLRenderer])
@parser_classes([FormParser, MultiPartParser])
def edit_profile(request):
    if request.method == "POST":
        profile_form = UserForm(request.data, instance=request.user)
        if profile_form.is_valid():
            profile_form.save()
            context = {
                "profile": request.user,
                "success": True,
                "toast_message": "Profile updated!",
                "toast_type": "success",
            }
        else:
            context = {
                "profile": request.user,
                "form": profile_form,
                "errors": profile_form.errors,
                "toast_message": "Error updating profile",
                "toast_type": "error",
            }
        return render_xml_frag("edit_profile.xml", "edit-profile", context)
    else:
        return render_xml(request, "edit_profile.xml", {"profile": request.user})


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@renderer_classes([XMLRenderer])
@parser_classes([FormParser, MultiPartParser])
def ask_question(request):
    questions_form = QuestionsForm(request.data)
    if request.method == "POST":
        context = {}
        if questions_form.is_valid():
            context.update(
                {
                    "success": True,
                    "toast_message": "Question sent!",
                    "toast_type": "success",
                }
            )
            EmailService.send_plain(
                f"{request.user.first_name} ({request.user.email}) asked a question",
                questions_form.cleaned_data.get("question", ""),
                "ari@usetimary.com",
            )
        else:
            context.update(
                {
                    "errors": questions_form.errors,
                    "toast_message": "Error sending the question",
                    "toast_type": "error",
                }
            )
        return render_xml_frag("questions.xml", "question-form", context)
    else:
        return render_xml(
            request,
            "questions.xml",
        )
