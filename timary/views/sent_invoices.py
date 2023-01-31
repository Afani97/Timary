from datetime import date
from uuid import UUID

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

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
            request, "partials/_sent_invoice.html", {"_sent_invoice": sent_invoice}
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

    month_sent = date.strftime(sent_invoice.date_sent, "%m/%Y")
    msg_body = InvoiceBuilder(invoice.user).send_invoice(
        {
            "sent_invoice": sent_invoice,
            "line_items": sent_invoice.get_rendered_line_items(),
        }
    )
    EmailService.send_html(
        f"{invoice.title}'s Invoice from {invoice.user.first_name} for {month_sent}",
        msg_body,
        invoice.client_email,
    )

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
                "not_started_count": sent_invoices.filter(
                    paid_status=SentInvoice.PaidStatus.NOT_STARTED
                ).count(),
                "pending_count": sent_invoices.filter(
                    paid_status=SentInvoice.PaidStatus.PENDING
                ).count(),
                "paid_count": sent_invoices.filter(
                    paid_status=SentInvoice.PaidStatus.PAID
                ).count(),
                "failed_count": sent_invoices.filter(
                    paid_status=SentInvoice.PaidStatus.FAILED
                ).count(),
                "cancelled_count": sent_invoices.filter(
                    paid_status=SentInvoice.PaidStatus.CANCELLED
                ).count(),
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
    if isinstance(sent_invoice.invoice, SingleInvoice):
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