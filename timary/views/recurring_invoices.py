from datetime import date, datetime

from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.http import Http404, HttpResponse, QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from timary.forms import HoursLineItemForm, InvoiceForm
from timary.invoice_builder import InvoiceBuilder
from timary.models import Invoice, InvoiceManager, SentInvoice, SingleInvoice
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
@require_http_methods(["GET", "POST"])
def create_invoice(request):
    if request.method == "GET":
        invoice_form_class, template = InvoiceManager.get_form(request.GET.get("type"))
        invoice_form = invoice_form_class(user=request.user)
        return render(request, template, {"form": invoice_form})

    invoice_form_class, template = InvoiceManager.get_form(
        request.POST.get("invoice_type")
    )
    invoice_form = invoice_form_class(request.POST or None, user=request.user)

    if not invoice_form.is_valid():
        response = render(request, template, {"form": invoice_form})
        response["HX-Retarget"] = "#new-invoice-form"
        response["HX-Reswap"] = "outerHTML"
        return response

    prev_invoice_count = request.user.get_invoices.count()
    invoice = invoice_form.save(commit=False)
    invoice.user = request.user
    # If user selects from list of contacts, get that contact's info
    if contact_id := invoice_form.cleaned_data.get("contacts"):
        contact = Invoice.objects.filter(client_stripe_customer_id=contact_id).first()
        invoice.client_email = contact.client_email
        invoice.client_name = contact.client_name
        invoice.client_stripe_customer_id = contact.client_stripe_customer_id
        invoice.accounting_customer_id = contact.accounting_customer_id
        invoice.save()
    invoice.update()
    invoice.save()
    invoice.sync_customer()

    response = render(request, "partials/_invoice.html", {"invoice": invoice})
    response["HX-Trigger-After-Swap"] = "clearInvoiceModal"  # To trigger modal closing
    # "newInvoice" - To trigger button refresh
    show_alert_message(response, "success", "New invoice created!", "newInvoice")
    if prev_invoice_count == 0:
        response["HX-Redirect"] = "/main/"  # To trigger refresh to remove empty state
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
    invoice = InvoiceManager(invoice_id).invoice
    if request.user != invoice.user:
        raise Http404
    invoice.is_paused = not invoice.is_paused
    if invoice.next_date <= date.today():
        invoice.calculate_next_date(update_last=True)
    invoice.save()
    response = render(request, "partials/_invoice.html", {"invoice": invoice})
    show_alert_message(
        response,
        "info",
        f"{invoice.title} has been {'paused' if invoice.is_paused else 'unpaused'}",
    )
    return response


@login_required()
@require_http_methods(["GET"])
def archive_invoice(request, invoice_id):
    invoice = InvoiceManager(invoice_id).invoice
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
    invoice = InvoiceManager(invoice_id).invoice
    if request.user != invoice.user:
        raise Http404
    form = invoice.form_class("update")(instance=invoice, user=request.user)
    return render(
        request, f"invoices/{invoice.invoice_type()}/_update.html", {"form": form}
    )


@login_required()
@require_http_methods(["PUT"])
def update_invoice(request, invoice_id):
    invoice = InvoiceManager(invoice_id).invoice
    if request.user != invoice.user:
        raise Http404
    put_params = QueryDict(request.body).copy()
    prev_invoice_interval_type = (
        invoice.invoice_interval if invoice.invoice_type() == "internal" else None
    )
    invoice_form = invoice.form_class("update")(
        put_params, instance=invoice, user=request.user
    )
    if invoice_form.is_valid():
        saved_invoice = invoice_form.save()
        if (
            prev_invoice_interval_type
            and invoice.invoice_type() == "internal"
            and prev_invoice_interval_type != saved_invoice.invoice_interval
            and not invoice.is_paused
        ):
            saved_invoice.calculate_next_date(update_last=False)
        response = render(request, "partials/_invoice.html", {"invoice": saved_invoice})
        show_alert_message(response, "success", f"{saved_invoice.title} was updated.")
        return response
    else:
        return render(
            request,
            f"invoices/{invoice.invoice_type()}/_update.html",
            {"form": invoice_form},
        )


@login_required()
@require_http_methods(["PUT"])
def update_invoice_next_date(request, invoice_id):
    invoice = InvoiceManager(invoice_id).invoice
    if request.user != invoice.user:
        raise Http404
    put_params = QueryDict(request.body).copy()
    next_date = datetime.strptime(
        put_params.get(f"start_on_{invoice.email_id}"), "%Y-%m-%d"
    ).date()
    next_date_updated = False
    if next_date > date.today():
        invoice.next_date = next_date
        invoice.save()
        next_date_updated = True
    response = render(request, "partials/_invoice_next_date.html", {"invoice": invoice})
    if next_date_updated:
        show_alert_message(response, "success", f"{invoice.title} was updated.")
    else:
        show_alert_message(
            response,
            "error",
            f"{invoice.title} cannot be updated. Must set date greater than today.",
            persist=True,
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
def generate_invoice(request, invoice_id):
    invoice = InvoiceManager(invoice_id).invoice
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
        invoice.invoice_type() == "milestone"
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
        f"Invoice for {invoice.title} has been sent to {invoice.client_name}",
    )
    return response


@login_required()
@require_http_methods(["GET"])
def edit_invoice_hours(request, invoice_id):
    invoice = InvoiceManager(invoice_id).invoice
    if request.user != invoice.user:
        raise Http404
    hours = invoice.get_hours_tracked()
    hour_forms = [HoursLineItemForm(instance=hour, user=request.user) for hour in hours]
    return render(request, "partials/_edit_hours.html", {"hour_forms": hour_forms})


@login_required()
@require_http_methods(["GET"])
def invoice_hour_stats(request, invoice_id):
    invoice = InvoiceManager(invoice_id).invoice
    if request.user != invoice.user:
        raise Http404
    return render(request, "partials/_invoice_period_hours.html", {"invoice": invoice})


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
def sync_invoice(request, invoice_id):
    invoice = InvoiceManager(invoice_id).invoice
    if request.user != invoice.user:
        raise Http404

    if not invoice.user.settings["subscription_active"]:
        response = render(
            request, "partials/_archive_invoice.html", {"archive_invoice": invoice}
        )
        show_alert_message(
            response,
            "warning",
            "Unable to sync invoice, your subscription is inactive.",
        )
        return response

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
