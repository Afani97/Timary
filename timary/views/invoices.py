from datetime import date

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.http import Http404, HttpResponse, QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from timary.forms import DailyHoursForm, InvoiceForm
from timary.models import Invoice, SentInvoice, User
from timary.services.email_service import EmailService
from timary.tasks import send_invoice
from timary.utils import show_active_timer, show_alert_message


@login_required()
@require_http_methods(["GET"])
def manage_invoices(request):
    invoices = request.user.get_invoices.order_by("title")
    sent_invoices_owed = request.user.sent_invoices.filter(
        ~Q(paid_status=SentInvoice.PaidStatus.PAID)
    ).aggregate(total=Sum("total_price"))
    sent_invoices_owed = (
        sent_invoices_owed["total"] if sent_invoices_owed["total"] else 0
    )

    sent_invoices_paid = request.user.sent_invoices.filter(
        paid_status=SentInvoice.PaidStatus.PAID
    ).aggregate(total=Sum("total_price"))
    sent_invoices_paid = (
        sent_invoices_paid["total"] if sent_invoices_paid["total"] else 0
    )

    context = {
        "invoices": invoices,
        "new_invoice": InvoiceForm(user=request.user),
        "sent_invoices_owed": sent_invoices_owed,
        "sent_invoices_earned": sent_invoices_paid,
        "archived_invoices": request.user.invoices.filter(is_archived=True),
    }
    context.update(show_active_timer(request.user))
    return render(
        request,
        "invoices/manage_invoices.html",
        context,
    )


@login_required()
@require_http_methods(["POST"])
def create_invoice(request):
    user: User = request.user
    request_data = request.POST.copy()
    if int(request_data.get("invoice_type")) == Invoice.InvoiceType.WEEKLY:
        request_data.update({"invoice_rate": request_data["weekly_rate"]})

    invoice_form = InvoiceForm(request_data or None, user=user)

    if invoice_form.is_valid():
        prev_invoice_count = user.get_invoices.count()
        invoice = invoice_form.save(commit=False)
        invoice.user = user
        if start_on := invoice_form.cleaned_data.get("start_on"):
            invoice.next_date = start_on
            invoice.last_date = date.today()
        else:
            invoice.calculate_next_date()
        invoice.save()
        invoice.sync_customer()

        response = render(request, "partials/_invoice.html", {"invoice": invoice})
        response[
            "HX-Trigger-After-Swap"
        ] = "clearInvoiceModal"  # To trigger modal closing
        # "newInvoice" - To trigger button refresh
        show_alert_message(response, "success", "New invoice created!", "newInvoice")
        if prev_invoice_count == 0:
            response[
                "HX-Redirect"
            ] = "/main/"  # To trigger refresh to remove empty state
        return response
    else:
        response = render(request, "invoices/_create.html", {"form": invoice_form})
        response["HX-Retarget"] = "#new-invoice-form"
        response["HX-Reswap"] = "outerHTML"
        return response


@login_required()
@require_http_methods(["GET"])
def get_invoice(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    if request.user != invoice.user:
        raise Http404
    return render(request, "partials/_invoice.html", {"invoice": invoice})


@login_required()
@require_http_methods(["GET"])
def pause_invoice(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    if request.user != invoice.user:
        raise Http404
    paused = False
    if invoice.next_date:
        paused = True
        invoice.next_date = None
    else:
        invoice.calculate_next_date(update_last=False)
    invoice.save()
    response = render(request, "partials/_invoice.html", {"invoice": invoice})
    show_alert_message(
        response,
        "info",
        f"{invoice.title} has been {'paused' if paused else 'unpaused'}",
    )
    return response


@login_required()
@require_http_methods(["GET"])
def archive_invoice(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    if request.user != invoice.user:
        raise Http404
    invoice.is_archived = True
    invoice.save()
    response = HttpResponse("", status=200)
    if request.user.get_invoices.count() == 0:
        response["HX-Refresh"] = "true"  # To trigger refresh to restore empty state
    else:
        # "newInvoice" - To trigger button refresh
        show_alert_message(
            response, "success", f"{invoice.title} was archived", "newInvoice"
        )
    return response


@login_required()
@require_http_methods(["GET"])
def edit_invoice(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    if request.user != invoice.user:
        raise Http404
    invoice_form = InvoiceForm(instance=invoice, user=request.user)
    return render(request, "invoices/_update.html", {"form": invoice_form})


@login_required()
@require_http_methods(["PUT"])
def update_invoice(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    if request.user != invoice.user:
        raise Http404
    put_params = QueryDict(request.body).copy()
    if invoice.invoice_type == Invoice.InvoiceType.WEEKLY:
        put_params.update({"invoice_rate": put_params["weekly_rate"]})
    invoice_form = InvoiceForm(put_params, instance=invoice, user=request.user)
    if invoice_form.is_valid():
        invoice = invoice_form.save()
        if invoice.next_date:
            invoice.calculate_next_date(update_last=False)
        response = render(request, "partials/_invoice.html", {"invoice": invoice})
        show_alert_message(response, "success", f"{invoice.title} was updated.")
        return response
    else:
        return render(request, "invoices/_update.html", {"form": invoice_form})


@login_required()
@require_http_methods(["GET"])
def resend_invoice_email(request, sent_invoice_id):
    sent_invoice = get_object_or_404(SentInvoice, id=sent_invoice_id)
    if sent_invoice.paid_status == SentInvoice.PaidStatus.PAID:
        return redirect(reverse("timary:user_profile"))
    invoice = sent_invoice.invoice
    if request.user != invoice.user:
        raise Http404
    month_sent = date.strftime(sent_invoice.date_sent, "%m/%Y")
    hours_tracked, total_amount = sent_invoice.get_hours_tracked()

    msg_subject = (
        f"{invoice.title}'s Invoice from {invoice.user.first_name} for {month_sent}"
    )

    msg_body = render_to_string(
        "email/sent_invoice_email.html",
        {
            "can_accept_payments": invoice.user.can_accept_payments,
            "site_url": settings.SITE_URL,
            "user_name": invoice.user.invoice_branding_properties()["user_name"],
            "next_weeks_date": invoice.user.invoice_branding_properties()[
                "next_weeks_date"
            ],
            "recipient_name": invoice.email_recipient_name,
            "total_amount": total_amount,
            "sent_invoice": sent_invoice,
            "invoice": invoice,
            "hours_tracked": hours_tracked,
            "todays_date": sent_invoice.date_sent,
            "invoice_branding": invoice.user.invoice_branding_properties(),
        },
    )
    EmailService.send_html(msg_subject, msg_body, invoice.email_recipient)

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
def generate_invoice(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    if request.user != invoice.user:
        raise Http404
    if not request.user.settings["subscription_active"]:
        response = render(request, "partials/_invoice.html", {"invoice": invoice})
        show_alert_message(
            response,
            "warning",
            "Your account is in-active. Please re-activate to generate an invoice.",
            persist=True,
        )
        return response
    if (
        invoice.invoice_type == Invoice.InvoiceType.MILESTONE
        and invoice.milestone_step > invoice.milestone_total_steps
    ):
        response = render(request, "partials/_invoice.html", {"invoice": invoice})
        show_alert_message(
            response,
            "info",
            f"{invoice.title} has completed all the milestones",
        )
        return response
    if invoice.get_hours_tracked().count() == 0:
        response = render(request, "partials/_invoice.html", {"invoice": invoice})
        show_alert_message(
            response,
            "info",
            f"{invoice.title} does not have hours logged yet to invoice",
        )
        return response

    # If invoice has hours to log and/or milestones, send invoice then
    send_invoice(invoice.id)
    invoice.refresh_from_db()

    response = render(request, "partials/_invoice.html", {"invoice": invoice})

    show_alert_message(
        response,
        "success",
        f"Invoice for {invoice.title} has been sent to {invoice.email_recipient_name}",
    )
    return response


@login_required()
@require_http_methods(["GET"])
def edit_invoice_hours(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    if request.user != invoice.user:
        raise Http404
    hours = invoice.get_hours_tracked()
    hour_forms = [DailyHoursForm(instance=hour, user=request.user) for hour in hours]
    return render(request, "partials/_edit_hours.html", {"hour_forms": hour_forms})


@login_required()
@require_http_methods(["GET"])
def invoice_hour_stats(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    if request.user != invoice.user:
        raise Http404
    return render(
        request, "partials/_invoice_collapsed_content.html", {"invoice": invoice}
    )


@login_required()
@require_http_methods(["GET"])
def sent_invoices_list(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    if request.user != invoice.user:
        raise Http404
    sent_invoices = SentInvoice.objects.filter(invoice=invoice).order_by("-date_sent")
    if sent_invoices:
        return render(
            request,
            "partials/_sent_invoices_list.html",
            {"sent_invoices": sent_invoices},
        )
    else:
        return_message = (
            "Looks like you haven't generated an invoice yet, log hours to do so."
        )
        if invoice.invoice_type == Invoice.InvoiceType.WEEKLY:
            return_message = "Looks like there haven't been any invoices sent yet."
        if invoice.is_archived:
            return_message = "There weren't any invoices sent."
        return HttpResponse(return_message)


@login_required()
@require_http_methods(["GET"])
def sync_invoice(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    if request.user != invoice.user:
        raise Http404

    customer_synced, error_raised = invoice.sync_customer()
    if invoice.is_archived:
        response = render(
            request, "partials/_archive_invoice.html", {"archive_invoice": invoice}
        )
    else:
        response = render(request, "partials/_invoice.html", {"invoice": invoice})

    if customer_synced:
        show_alert_message(
            response,
            "success",
            f"{invoice.title} is now synced with {invoice.user.accounting_org}",
        )
    else:
        show_alert_message(
            response,
            "error",
            f"We had trouble syncing {invoice.title}. {error_raised}",
            persist=True,
        )
    return response


@login_required()
@require_http_methods(["GET"])
def sync_sent_invoice(request, sent_invoice_id):
    sent_invoice = get_object_or_404(SentInvoice, id=sent_invoice_id)
    if request.user != sent_invoice.user:
        raise Http404

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
