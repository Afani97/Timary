from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django_q.tasks import schedule

from timary.forms import LineItemForm, SingleInvoiceForm
from timary.models import LineItem, SentInvoice, SingleInvoice
from timary.tasks import send_invoice_installment, send_invoice_reminder
from timary.utils import get_users_localtime, show_alert_message


def format_line_items(request):
    line_items = []
    for line_item_id, description, quantity, price in zip(
        request.POST.getlist("id"),
        request.POST.getlist("description"),
        request.POST.getlist("quantity"),
        request.POST.getlist("unit_price"),
    ):
        line_item = None
        if len(line_item_id) > 0:
            try:
                line_item = LineItem.objects.get(id=line_item_id)
            except LineItem.DoesNotExist:
                pass
        form_args = {
            "data": {
                "description": description,
                "quantity": quantity,
                "unit_price": price,
            }
        }
        if line_item:
            form_args.update({"instance": line_item})
        line_form = LineItemForm(**form_args)
        line_items.append(line_form)
    return line_items


@login_required()
@require_http_methods(["GET", "POST"])
def single_invoice(request):
    if request.method == "GET":
        return render(
            request,
            "invoices/single_invoice.html",
            {
                "invoice_form": SingleInvoiceForm(user=request.user),
                "line_item_forms": [LineItemForm()],
            },
        )
    elif request.method == "POST":
        invoice_form = SingleInvoiceForm(request.POST, user=request.user)
        if not invoice_form.is_valid():
            messages.warning(
                request,
                "Errors occurred while creating invoice",
                extra_tags="single-invoice-err",
            )
            return render(
                request,
                "invoices/single_invoice.html",
                {
                    "invoice_form": invoice_form,
                    "line_item_forms": format_line_items(request),
                },
            )

        saved_single_invoice = invoice_form.save(commit=False)
        saved_single_invoice.user = request.user
        saved_single_invoice.save()

        # Save line items to the invoice if valid
        for line_form in format_line_items(request):
            if line_form.is_valid():
                line_item_saved = line_form.save(commit=False)
                line_item_saved.invoice = saved_single_invoice
                line_item_saved.save()
        saved_single_invoice.update()
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

    raise Http404()


@login_required()
@require_http_methods(["GET", "POST", "DELETE"])
def update_single_invoice(request, single_invoice_id):
    single_invoice_obj = get_object_or_404(SingleInvoice, id=single_invoice_id)
    if single_invoice_obj.user != request.user:
        return redirect(reverse("timary:login"))
    invoice_form = SingleInvoiceForm(
        request.POST or None, instance=single_invoice_obj, user=request.user
    )
    line_item_forms = [
        LineItemForm(instance=line_item)
        for line_item in single_invoice_obj.line_items.all()
    ]
    if request.method == "DELETE":
        single_invoice_obj.is_archived = True
        single_invoice_obj.save()
        response = HttpResponse()
        response["HX-Redirect"] = "/invoices/manage/"
        return response
    if request.method == "POST":
        prev_installment = single_invoice_obj.installments
        if not invoice_form.is_valid():
            messages.warning(
                request,
                "Errors occurred while updating invoice",
                extra_tags="single-invoice-err",
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

        saved_single_invoice: SingleInvoice = invoice_form.save(commit=False)
        saved_single_invoice.user = request.user
        saved_single_invoice.save()
        # Save line items to the invoice if valid
        for line_form in format_line_items(request):
            if line_form.is_valid():
                line_item_saved = line_form.save(commit=False)
                line_item_saved.invoice = saved_single_invoice
                line_item_saved.save()

        saved_single_invoice.update()
        if (
            prev_installment > 1
            and saved_single_invoice.installments > prev_installment
        ):
            saved_single_invoice.update_next_installment_date()
        single_invoice_obj = saved_single_invoice
        line_item_forms = [
            LineItemForm(instance=line_item)
            for line_item in saved_single_invoice.line_items.all()
        ]
        messages.success(
            request,
            f"Updated {saved_single_invoice.title}",
            extra_tags="update-single-invoice",
        )
        if single_invoice_obj.installments == 1:
            send_url = reverse(
                "timary:send_single_invoice_email",
                kwargs={"single_invoice_id": saved_single_invoice.id},
            )
            messages.info(
                request,
                {
                    "msg": "Resend the invoice?",
                    "link": f"{send_url}?from_update=true",
                },
                extra_tags="send-single-invoice",
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
                "line_item_form": LineItemForm(),
            },
        )
    if request.method == "DELETE":
        line_item_id = request.GET.get("line_item_id")
        line_item = get_object_or_404(LineItem, id=line_item_id)
        line_item.delete()
        return HttpResponse("")
    raise Http404


@login_required()
@require_http_methods(["GET"])
def sync_single_invoice(request, single_invoice_id):
    single_invoice_obj = get_object_or_404(SingleInvoice, id=single_invoice_id)
    if request.user != single_invoice_obj.user:
        raise Http404

    template = "_single_invoice"
    if single_invoice_obj.is_archived:
        template = "_archive_template"
    response = render(
        request,
        f"partials/{template}.html",
        {"single_invoice": single_invoice_obj},
    )

    if single_invoice_obj.accounting_customer_id is None:
        customer_synced, error_raised = single_invoice_obj.sync_customer()
        if customer_synced:
            show_alert_message(
                response,
                "success",
                f"{single_invoice_obj.client.name.title()} is "
                f"now synced with {single_invoice_obj.user.accounting_org}",
            )
        else:
            show_alert_message(
                response,
                "error",
                f"We had trouble syncing {single_invoice_obj.client.name.title()}. {error_raised}",
                persist=True,
            )
        return response
    else:
        if (
            single_invoice_obj.installments == 1
            and single_invoice_obj.get_sent_invoice()
        ):
            (
                invoice_synced,
                error_raised,
            ) = single_invoice_obj.get_sent_invoice().sync_invoice()
            if invoice_synced:
                show_alert_message(
                    response,
                    "success",
                    f"{single_invoice_obj.title}'s paid invoice is "
                    f"now synced with {single_invoice_obj.user.accounting_org}",
                )
            else:
                show_alert_message(
                    response,
                    "error",
                    f"We had trouble syncing {single_invoice_obj.title}'s paid invoice. {error_raised}",
                    persist=True,
                )
        return response


@login_required()
@require_http_methods(["GET"])
def update_single_invoice_status(request, single_invoice_id):
    single_invoice_obj = get_object_or_404(SingleInvoice, id=single_invoice_id)
    if request.user != single_invoice_obj.user:
        return redirect(reverse("timary:login"))

    if single_invoice_obj.status == SingleInvoice.InvoiceStatus.DRAFT:
        single_invoice_obj.status = SingleInvoice.InvoiceStatus.FINAL
    elif single_invoice_obj.status == SingleInvoice.InvoiceStatus.FINAL:
        single_invoice_obj.status = SingleInvoice.InvoiceStatus.DRAFT
    single_invoice_obj.save()
    response = render(
        request, "partials/_single_invoice.html", {"single_invoice": single_invoice_obj}
    )
    show_alert_message(
        response,
        "success",
        f"{single_invoice_obj.title} has been updated to {single_invoice_obj.get_status_display().title()}",
    )
    return response


@login_required()
@require_http_methods(["GET"])
def send_single_invoice_email(request, single_invoice_id):
    single_invoice_obj = get_object_or_404(SingleInvoice, id=single_invoice_id)
    if request.user != single_invoice_obj.user:
        raise Http404
    sent_invoice = single_invoice_obj.get_sent_invoice()
    invoice_is_paid = (
        sent_invoice is not None
        and sent_invoice.paid_status == SentInvoice.PaidStatus.PAID
    )

    # Send once done updating single invoice and sends from message link
    from_update_form = request.GET.get("from_update", False)
    if (
        not request.user.settings["subscription_active"]
        or invoice_is_paid
        or single_invoice_obj.status == SingleInvoice.InvoiceStatus.DRAFT
    ):
        response = render(
            request,
            "partials/_single_invoice.html",
            {"single_invoice": single_invoice_obj},
        )
        show_alert_message(
            response,
            "warning",
            "Unable to send out invoice.",
            persist=True,
        )
        return response

    if sent_invoice:
        sent_invoice.paid_status = SentInvoice.PaidStatus.NOT_STARTED
        sent_invoice.save()

    send_invoice_reminder(single_invoice_id)

    if single_invoice_obj.send_reminder:
        schedule(
            "timary.tasks.send_invoice_reminder",
            str(single_invoice_obj.id),
            schedule_type="O",
            next_run=get_users_localtime(request.user) + timezone.timedelta(weeks=2),
        )

    if from_update_form:
        response = HttpResponse(status=204)
    else:
        response = render(
            request,
            "partials/_single_invoice.html",
            {"single_invoice": single_invoice_obj, "invoice_resent": True},
        )
    show_alert_message(
        response,
        "success",
        f"Invoice for {single_invoice_obj.title} has been sent",
        persist=True,
    )
    return response


@login_required()
@require_http_methods(["GET"])
def send_first_installment(request, single_invoice_id):
    single_invoice_obj = get_object_or_404(SingleInvoice, id=single_invoice_id)
    if request.user != single_invoice_obj.user:
        raise Http404

    if (
        not request.user.settings["subscription_active"]
        or single_invoice_obj.status == SingleInvoice.InvoiceStatus.DRAFT
    ):
        response = render(
            request,
            "partials/_single_invoice.html",
            {"single_invoice": single_invoice_obj},
        )
        show_alert_message(
            response,
            "warning",
            "Unable to send out invoice.",
            persist=True,
        )
        return response

    if (
        single_invoice_obj.installments > 1
        and single_invoice_obj.invoice_snapshots.count() == 0
    ):
        single_invoice_obj.next_installment_date = timezone.now()
        single_invoice_obj.save()
        send_invoice_installment(single_invoice_obj.id)
        response = render(
            request,
            "partials/_single_invoice.html",
            {"single_invoice": single_invoice_obj, "installment_sent": True},
        )
        show_alert_message(
            response,
            "success",
            f"Installment for {single_invoice_obj.title} has been sent",
            persist=True,
        )
        return response
    else:
        response = render(
            request,
            "partials/_single_invoice.html",
            {"single_invoice": single_invoice_obj},
        )
        show_alert_message(
            response,
            "warning",
            "Unable to send out invoice.",
            persist=True,
        )
        return response
