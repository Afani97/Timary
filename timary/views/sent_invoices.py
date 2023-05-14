from io import BytesIO
from uuid import UUID

import qrcode
from django.contrib.auth.decorators import login_required
from django.core.files.storage import FileSystemStorage
from django.http import Http404, HttpResponse, QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from qrcode.image.svg import SvgPathFillImage
from weasyprint import CSS, HTML

from timary.forms import HoursLineItemForm
from timary.invoice_builder import InvoiceBuilder
from timary.models import HoursLineItem, InvoiceManager, SentInvoice, SingleInvoice
from timary.services.email_service import EmailService
from timary.utils import show_alert_message


@login_required()
@require_http_methods(["GET"])
def get_sent_invoice(request, sent_invoice_id):
    sent_invoice = get_object_or_404(SentInvoice, id=sent_invoice_id)
    if request.user != sent_invoice.invoice.user:
        raise Http404

    invoice = sent_invoice.invoice
    if (
        invoice.invoice_type() == "single"
        and invoice.installments == 1
        and not invoice.is_archived
    ):
        # To return the correct invoice card after closing a qr code
        response = render(
            request,
            "partials/_single_invoice.html",
            {"single_invoice": invoice},
        )
        response["HX-Retarget"] = f"#{invoice.slug_title}"
        return response

    response = render(
        request,
        "partials/_sent_invoice.html",
        {"sent_invoice": sent_invoice},
    )
    return response


@login_required()
@require_http_methods(["GET"])
def resend_invoice_email(request, sent_invoice_id):
    sent_invoice = get_object_or_404(SentInvoice, id=sent_invoice_id)
    if sent_invoice.paid_status == SentInvoice.PaidStatus.PAID:
        return redirect(reverse("timary:user_profile"))
    if not request.user.settings["subscription_active"]:
        response = render(
            request, "partials/_sent_invoice.html", {"sent_invoice": sent_invoice}
        )
        show_alert_message(
            response,
            "warning",
            "Your account is in-active. Please re-activate to resend an invoice.",
            persist=True,
        )
        return response
    invoice = sent_invoice.invoice
    if request.user != invoice.user:
        raise Http404

    sent_invoice.paid_status = SentInvoice.PaidStatus.NOT_STARTED
    sent_invoice.save(update_fields=["paid_status"])
    if (
        isinstance(sent_invoice.invoice, SingleInvoice)
        and sent_invoice.invoice.installments > 1
    ):
        sent_invoice.update_installments()

    msg_body = InvoiceBuilder(invoice.user).send_invoice(
        {
            "sent_invoice": sent_invoice,
            "line_items": sent_invoice.get_rendered_line_items(),
        }
    )
    msg_subject = (
        f"{invoice.title}'s Invoice from {invoice.user.first_name} is ready to view."
    )
    EmailService.send_html(
        msg_subject,
        msg_body,
        invoice.client.email,
    )
    sent_invoice.send_sms_message(msg_subject)

    response = render(
        request,
        "partials/_sent_invoice.html",
        {"sent_invoice": sent_invoice, "invoice_resent": True},
    )
    show_alert_message(
        response,
        "success",
        f"Invoice for {invoice.title} has been resent",
    )
    return response


@login_required()
@require_http_methods(["GET"])
def sent_invoices_list(request, invoice_id):
    invoice = InvoiceManager(invoice_id).invoice
    if request.user != invoice.user:
        raise Http404
    sent_invoices = SentInvoice.objects.filter(invoice=invoice).order_by("-date_sent")
    if sent_invoices:
        return render(
            request,
            "partials/_sent_invoices_list.html",
            {
                "sent_invoices": sent_invoices,
            },
        )
    else:
        return_message = (
            "Looks like you haven't generated an invoice yet, log hours to do so."
        )
        if invoice.invoice_type() == "weekly":
            return_message = "Looks like there haven't been any invoices sent yet."
        if invoice.is_archived:
            return_message = "There weren't any invoices sent."
        return HttpResponse(return_message)


@login_required()
@require_http_methods(["GET"])
def sync_sent_invoice(request, sent_invoice_id):
    sent_invoice = get_object_or_404(SentInvoice, id=sent_invoice_id)
    if request.user != sent_invoice.user:
        raise Http404

    if not request.user.settings["subscription_active"]:
        response = render(
            request, "partials/_sent_invoice.html", {"sent_invoice": sent_invoice}
        )
        show_alert_message(
            response,
            "error",
            "Your account is in-active. Please re-activate to sync your invoices.",
            persist=True,
        )
        return response

    invoice_synced, error_raised = sent_invoice.sync_invoice()
    response = render(
        request, "partials/_sent_invoice.html", {"sent_invoice": sent_invoice}
    )

    if invoice_synced:
        show_alert_message(
            response,
            "success",
            f"{sent_invoice.invoice.title} is now synced with {sent_invoice.invoice.user.accounting_org.title()}",
        )
    else:
        show_alert_message(
            response,
            "error",
            f"We had trouble syncing this sent invoice. {error_raised}",
            persist=True,
        )
    return response


@login_required()
@require_http_methods(["GET"])
def cancel_invoice(request, sent_invoice_id):
    sent_invoice = get_object_or_404(SentInvoice, id=sent_invoice_id)
    if request.user != sent_invoice.user:
        raise Http404
    if sent_invoice.paid_status not in [
        SentInvoice.PaidStatus.NOT_STARTED,
        SentInvoice.PaidStatus.FAILED,
    ]:
        response = HttpResponse()
        show_alert_message(response, "warning", "Unable to cancel invoice")
        return response
    sent_invoice.paid_status = SentInvoice.PaidStatus.CANCELLED
    sent_invoice.save()
    if (
        isinstance(sent_invoice.invoice, SingleInvoice)
        and not sent_invoice.invoice.is_archived
    ):
        response = render(
            request,
            "partials/_single_invoice.html",
            {"single_invoice": sent_invoice.invoice},
        )
    else:
        response = render(
            request, "partials/_sent_invoice.html", {"sent_invoice": sent_invoice}
        )
    show_alert_message(
        response,
        "info",
        f"{sent_invoice.invoice.title} has been cancelled",
    )
    return response


@login_required()
@require_http_methods(["GET", "PATCH", "PUT", "DELETE"])
def edit_sent_invoice_hours(request, sent_invoice_id):
    sent_invoice = get_object_or_404(SentInvoice, id=sent_invoice_id)
    if request.user != sent_invoice.user:
        raise Http404

    if sent_invoice.paid_status not in [
        SentInvoice.PaidStatus.NOT_STARTED,
        SentInvoice.PaidStatus.FAILED,
    ]:
        response = HttpResponse()
        show_alert_message(response, "warning", "Unable to edit hours")
        return response

    if request.method == "GET":
        hours = sent_invoice.get_hours_tracked()
        hour_forms = [
            HoursLineItemForm(instance=hour, user=request.user) for hour in hours
        ]
        return render(
            request,
            "partials/_edit_sent_hours.html",
            {"hour_forms": hour_forms, "sent_invoice": sent_invoice},
        )
    if request.method == "PATCH":
        request_data = QueryDict(request.body, mutable=True)
        hour_id = request_data.get("hour_id")
        request_data.pop("hour_id")

        try:
            hours = HoursLineItem.objects.get(id=UUID(hour_id))
        except HoursLineItem.DoesNotExist:
            return redirect(reverse("timary:login"))
        request_data.update({"date_tracked": hours.date_tracked})
        hours_form = HoursLineItemForm(request_data, instance=hours, user=request.user)
        ctx = {"form": hours_form, "sent_invoice": sent_invoice}
        if hours_form.is_valid():
            hours_form.save()
            sent_invoice.update_total_price()
            ctx.update({"success_msg": "Successfully updated hours!"})
        return render(
            request,
            "partials/_patch_sent_invoice_hour.html",
            ctx,
        )
    if request.method == "DELETE":
        hour_id = request.GET.get("hour_id", None)
        hours = HoursLineItem.objects.get(id=hour_id)
        if sent_invoice.get_hours_tracked().count() == 1:
            response = render(
                request,
                "partials/_patch_sent_invoice_hour.html",
                {
                    "form": HoursLineItemForm(instance=hours, user=request.user),
                    "sent_invoice": sent_invoice,
                },
            )
            show_alert_message(
                response, "warning", "The sent invoice needs at least one line item."
            )
            return response
        if hours:
            hours.delete()
            sent_invoice.update_total_price()
            return HttpResponse("")
        else:
            return HttpResponse("", status=401)

    if request.method == "PUT":
        sent_invoice.update_total_price()
        request.method = "GET"  # Trick Django into allowing this
        _ = resend_invoice_email(request, sent_invoice.id)
        response = sent_invoices_list(request, sent_invoice.invoice.id)
        show_alert_message(response, "success", "Sent updated invoice")
        return response
    raise Http404()


@login_required()
@require_http_methods(["GET", "PATCH", "PUT", "DELETE"])
def download_sent_invoice_copy(request, sent_invoice_id):
    sent_invoice = get_object_or_404(SentInvoice, id=sent_invoice_id)
    if request.user != sent_invoice.user:
        raise Http404

    html = HTML(
        string=render_to_string(
            "invoices/print/print.html",
            {
                "sent_invoice": sent_invoice,
                "client": sent_invoice.invoice.client,
                "user": sent_invoice.user,
                "line_items": sent_invoice.get_line_items(),
                "user_timezone": sent_invoice.user.timezone,
            },
        )
    )
    stylesheet = CSS(string=render_to_string("invoices/print/print.css", {}))
    html.write_pdf(target="/tmp/mypdf.pdf", stylesheets=[stylesheet])

    fs = FileSystemStorage("/tmp")
    with fs.open("mypdf.pdf") as pdf:
        response = HttpResponse(pdf, content_type="application/pdf")
        response[
            "Content-Disposition"
        ] = f'attachment; filename="sent_invoice_{sent_invoice.email_id}.pdf"'

    show_alert_message(
        response, "success", "You should see the pdf downloading shortly"
    )
    return response


@login_required()
@require_http_methods(["GET"])
def generate_qrcode_invoice(request, sent_invoice_id):
    sent_invoice = get_object_or_404(SentInvoice, id=sent_invoice_id)
    if request.user != sent_invoice.user:
        raise Http404

    sent_invoice.paid_status = SentInvoice.PaidStatus.NOT_STARTED
    sent_invoice.save()

    sent_invoice_url = request.build_absolute_uri(
        reverse("timary:pay_invoice", kwargs={"sent_invoice_id": sent_invoice.id})
    )

    stream = BytesIO()
    img = qrcode.make(sent_invoice_url, image_factory=SvgPathFillImage)
    img.save(stream)

    ctx = {"qrcode_img": stream.getvalue().decode(), "sent_invoice_id": sent_invoice.id}
    return render(request, "partials/_qrcode.html", ctx)
