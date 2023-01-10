from datetime import date, datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.http import Http404, HttpResponse, QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from timary.forms import (
    CreateIntervalForm,
    CreateMilestoneForm,
    CreateWeeklyForm,
    DailyHoursForm,
    SingleInvoiceForm,
    SingleInvoiceLineItemForm,
    UpdateIntervalForm,
    UpdateMilestoneForm,
    UpdateWeeklyForm,
)
from timary.models import (
    Invoice,
    SentInvoice,
    SingleInvoice,
    SingleInvoiceLineItem,
    User,
)
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
        "single_invoices": request.user.single_invoices.exclude(
            status=SingleInvoice.InvoiceStatus.ARCHIVE
        ).order_by("title"),
        "sent_invoices_owed": sent_invoices_owed,
        "sent_invoices_earned": sent_invoices_paid,
        "archived_invoices": request.user.invoices.filter(is_archived=True),
        "archived_single_invoices": request.user.single_invoices.filter(
            status=SingleInvoice.InvoiceStatus.ARCHIVE
        ),
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
        invoice_form_class, template = get_invoice_form_class(
            Invoice.InvoiceType(int(request.GET.get("type")))
        )
        invoice_form = invoice_form_class(user=request.user)
        return render(
            request, f"invoices/{template}/_create.html", {"form": invoice_form}
        )
    user: User = request.user
    request_data = request.POST.copy()
    invoice_form_class, template = get_invoice_form_class(
        Invoice.InvoiceType(int(request_data.get("invoice_type")))
    )
    invoice_form = invoice_form_class(request_data, user=user)

    if invoice_form.is_valid():
        prev_invoice_count = user.get_invoices.count()
        invoice = invoice_form.save(commit=False)
        invoice.user = user
        # If user selects from list of contacts, get that contact's info
        if contact_id := invoice_form.cleaned_data.get("contacts"):
            contact = Invoice.objects.filter(
                client_stripe_customer_id=contact_id
            ).first()
            invoice.client_email = contact.client_email
            invoice.client_name = contact.client_name
            invoice.client_stripe_customer_id = contact.client_stripe_customer_id
            invoice.accounting_customer_id = contact.accounting_customer_id
            invoice.save()
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
        response = render(
            request, f"invoices/{template}/_create.html", {"form": invoice_form}
        )
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


def get_invoice_form_class(type, action="create"):
    if type == Invoice.InvoiceType.INTERVAL:
        invoice_form = CreateIntervalForm if action == "create" else UpdateIntervalForm
        template = "interval"
    elif type == Invoice.InvoiceType.MILESTONE:
        invoice_form = (
            CreateMilestoneForm if action == "create" else UpdateMilestoneForm
        )
        template = "milestone"
    else:
        invoice_form = CreateWeeklyForm if action == "create" else UpdateWeeklyForm
        template = "weekly"
    return invoice_form, template


@login_required()
@require_http_methods(["GET"])
def edit_invoice(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    if request.user != invoice.user:
        raise Http404
    invoice_form_class, template = get_invoice_form_class(
        invoice.invoice_type, action="update"
    )
    form = invoice_form_class(instance=invoice, user=request.user)
    return render(request, f"invoices/{template}/_update.html", {"form": form})


@login_required()
@require_http_methods(["PUT"])
def update_invoice(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    if request.user != invoice.user:
        raise Http404
    put_params = QueryDict(request.body).copy()
    put_params.update({"invoice_type": invoice.invoice_type})
    invoice_form_class, template = get_invoice_form_class(
        invoice.invoice_type, action="update"
    )
    prev_invoice_interval_type = (
        invoice.invoice_interval
        if invoice.invoice_type == Invoice.InvoiceType.INTERVAL
        else None
    )
    invoice_form = invoice_form_class(put_params, instance=invoice, user=request.user)
    if invoice_form.is_valid():
        saved_invoice = invoice_form.save()
        if (
            prev_invoice_interval_type
            and invoice.invoice_type == Invoice.InvoiceType.INTERVAL
            and prev_invoice_interval_type != saved_invoice.invoice_interval
            and not invoice.is_paused
        ):
            saved_invoice.calculate_next_date(update_last=False)
        response = render(request, "partials/_invoice.html", {"invoice": saved_invoice})
        show_alert_message(response, "success", f"{saved_invoice.title} was updated.")
        return response
    else:
        return render(
            request, f"invoices/{template}/_update.html", {"form": invoice_form}
        )


@login_required()
@require_http_methods(["PUT"])
def update_invoice_next_date(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
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
            "recipient_name": invoice.client_name,
            "total_amount": total_amount,
            "sent_invoice": sent_invoice,
            "invoice": invoice,
            "hours_tracked": hours_tracked,
            "todays_date": sent_invoice.date_sent,
            "invoice_branding": invoice.user.invoice_branding_properties(),
        },
    )
    EmailService.send_html(msg_subject, msg_body, invoice.client_email)

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
        f"Invoice for {invoice.title} has been sent to {invoice.client_name}",
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
    return render(request, "partials/_invoice_period_hours.html", {"invoice": invoice})


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
            },
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
@require_http_methods(["GET", "POST"])
def single_invoice(request):
    if request.method == "GET":
        return render(
            request,
            "invoices/single_invoice.html",
            {
                "invoice_form": SingleInvoiceForm(),
                "line_item_forms": [SingleInvoiceLineItemForm()],
            },
        )
    elif request.method == "POST":
        invoice_form = SingleInvoiceForm(request.POST)
        if len(request.POST.getlist("description")) == 0:
            invoice_form.add_error(None, "Invoice needs at least one line item")
            return render(
                request,
                "invoices/single_invoice.html",
                {
                    "invoice_form": invoice_form,
                    "line_item_forms": [SingleInvoiceLineItemForm()],
                },
            )
        if invoice_form.is_valid():
            saved_single_invoice = invoice_form.save(commit=False)
            saved_single_invoice.user = request.user
            if invoice_status := request.GET.get("status"):
                if invoice_status == "draft":
                    saved_single_invoice.status = SingleInvoice.InvoiceStatus.DRAFT
                elif invoice_status == "send":
                    saved_single_invoice.status = SingleInvoice.InvoiceStatus.SENT
            saved_single_invoice.save()

            # Save line items to the invoice if valid
            for description, quantity, price in zip(
                request.POST.getlist("description"),
                request.POST.getlist("quantity"),
                request.POST.getlist("price"),
            ):
                line_form = SingleInvoiceLineItemForm(
                    data={
                        "description": description,
                        "quantity": quantity,
                        "price": price,
                    }
                )
                if line_form.is_valid():
                    line_item_saved = line_form.save(commit=False)
                    line_item_saved.invoice = saved_single_invoice
                    line_item_saved.save()
            saved_single_invoice.update_total_price()
            if saved_single_invoice.status == SingleInvoice.InvoiceStatus.SENT:
                saved_single_invoice.send_invoice()
            messages.success(
                request,
                f"Successfully created {saved_single_invoice.title}",
                extra_tags="new-single-invoice",
            )
            return redirect(
                reverse(
                    "timary:update_single_invoice",
                    kwargs={"single_invoice_id": saved_single_invoice.id},
                )
            )
        else:
            return render(
                request,
                "invoices/single_invoice.html",
                {
                    "invoice_form": invoice_form,
                    "line_item_forms": [SingleInvoiceLineItemForm()],
                },
            )

    raise Http404()


@login_required()
@require_http_methods(["GET", "POST", "DELETE"])
def update_single_invoice(request, single_invoice_id):
    single_invoice_obj = get_object_or_404(SingleInvoice, id=single_invoice_id)
    invoice_form = SingleInvoiceForm(request.POST or None, instance=single_invoice_obj)
    line_item_forms = [
        SingleInvoiceLineItemForm(instance=line_item)
        for line_item in single_invoice_obj.line_items.all()
    ]
    if request.method == "DELETE":
        single_invoice_obj.status = SingleInvoice.InvoiceStatus.ARCHIVE
        single_invoice_obj.save()
        response = HttpResponse()
        response["HX-Redirect"] = "/invoices/manage/"
        return response
    if request.method == "POST":
        # Check that invoice has at least 1 line item before proceeding
        if len(request.POST.getlist("description")) == 0:
            invoice_form.add_error(None, "Invoice needs at least one line item")
            return render(
                request,
                "invoices/single_invoice.html",
                {
                    "single_invoice": single_invoice_obj,
                    "invoice_form": invoice_form,
                    "line_item_forms": [SingleInvoiceLineItemForm()],
                },
            )
        if invoice_form.is_valid():
            saved_single_invoice: SingleInvoice = invoice_form.save(commit=False)
            saved_single_invoice.user = request.user
            if invoice_status := request.GET.get("status"):
                if invoice_status == "draft":
                    saved_single_invoice.status = SingleInvoice.InvoiceStatus.DRAFT
                elif invoice_status == "send":
                    saved_single_invoice.status = SingleInvoice.InvoiceStatus.SENT
            saved_single_invoice.save()
            # Save line items to the invoice if valid
            for line_item_id, description, quantity, price in zip(
                request.POST.getlist("id"),
                request.POST.getlist("description"),
                request.POST.getlist("quantity"),
                request.POST.getlist("price"),
            ):
                line_item = None
                if len(line_item_id) > 0:
                    try:
                        line_item = SingleInvoiceLineItem.objects.get(id=line_item_id)
                    except SingleInvoiceLineItem.DoesNotExist:
                        pass
                form_args = {
                    "data": {
                        "description": description,
                        "quantity": quantity,
                        "price": price,
                    }
                }
                if line_item:
                    form_args.update({"instance": line_item})
                line_form = SingleInvoiceLineItemForm(**form_args)
                if line_form.is_valid():
                    line_item_saved = line_form.save(commit=False)
                    line_item_saved.invoice = saved_single_invoice
                    line_item_saved.save()

            saved_single_invoice.update_total_price()
            if saved_single_invoice.status == SingleInvoice.InvoiceStatus.SENT:
                saved_single_invoice.send_invoice()
            single_invoice_obj = saved_single_invoice
            line_item_forms = [
                SingleInvoiceLineItemForm(instance=line_item)
                for line_item in saved_single_invoice.line_items.all()
            ]
            messages.success(
                request,
                f"Updated {saved_single_invoice.title}",
                extra_tags="update-single-invoice",
            )
    return render(
        request,
        "invoices/single_invoice.html",
        {
            "single_invoice": single_invoice_obj,
            "invoice_form": invoice_form,
            "line_item_forms": line_item_forms,
        },
    )


@login_required()
@require_http_methods(["GET", "DELETE"])
def single_invoice_line_item(request):
    if request.method == "GET":
        return render(
            request,
            "partials/_single_invoice_line_item.html",
            {
                "line_item_form": SingleInvoiceLineItemForm(),
            },
        )
    if request.method == "DELETE":
        line_item_id = request.GET.get("line_item_id")
        line_item = get_object_or_404(SingleInvoiceLineItem, id=line_item_id)
        line_item.delete()
        return HttpResponse("")
    raise Http404


@login_required()
@require_http_methods(["GET"])
def sync_single_invoice(request, single_invoice_id):
    single_invoice_obj = get_object_or_404(SingleInvoice, id=single_invoice_id)
    if request.user != single_invoice_obj.user:
        raise Http404

    customer_synced, error_raised = single_invoice_obj.sync_customer()
    if single_invoice_obj.status < 3:
        response = render(
            request,
            "partials/_single_invoice.html",
            {"single_invoice": single_invoice_obj},
        )
    else:
        response = render(
            request,
            "partials/_archived_single_invoice.html",
            {"single_invoice": single_invoice_obj},
        )

    if customer_synced:
        invoice_synced, error_raised = single_invoice_obj.sync_invoice()

        if invoice_synced:
            show_alert_message(
                response,
                "success",
                f"{single_invoice_obj.title} is now synced with {single_invoice_obj.user.accounting_org}",
            )
            return response
    show_alert_message(
        response,
        "error",
        f"We had trouble syncing {single_invoice_obj.title}. {error_raised}",
        persist=True,
    )
    return response


@login_required()
@require_http_methods(["GET"])
def resend_single_invoice_email(request, single_invoice_id):
    single_invoice_obj = get_object_or_404(SingleInvoice, id=single_invoice_id)
    if single_invoice_obj.paid_status == SingleInvoice.PaidStatus.PAID:
        return redirect(reverse("timary:manage_invoices"))
    if not request.user.settings["subscription_active"]:
        response = render(
            request,
            "partials/_single_invoice.html",
            {"single_invoice": single_invoice_obj},
        )
        show_alert_message(
            response,
            "warning",
            "Your account is in-active. Please re-activate to resend an invoice.",
            persist=True,
        )
        return response
    if request.user != single_invoice_obj.user:
        raise Http404
    single_invoice_obj.send_invoice()

    response = render(
        request,
        "partials/_single_invoice.html",
        {"single_invoice": single_invoice_obj, "invoice_resent": True},
    )
    show_alert_message(
        response,
        "success",
        f"Invoice for {single_invoice_obj.title} has been resent",
    )
    return response
