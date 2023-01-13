from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from timary.forms import LineItemForm, SingleInvoiceForm
from timary.models import LineItem, SingleInvoice
from timary.utils import show_alert_message


def greater_than_one(x):
    return float(x) > 0


def validate_line_items(request):
    if len(request.POST.getlist("description")) == 0:
        raise ValidationError("Invoice needs at least one line item.")

    if not any(map(greater_than_one, request.POST.getlist("quantity"))) or not any(
        map(greater_than_one, request.POST.getlist("unit_price"))
    ):
        raise ValidationError(
            "Line items aren't valid, please set the price and quantity greater than 1."
        )


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
                "invoice_form": SingleInvoiceForm(),
                "line_item_forms": [LineItemForm()],
            },
        )
    elif request.method == "POST":
        invoice_form = SingleInvoiceForm(request.POST)
        try:
            validate_line_items(request)
        except ValidationError as e:
            messages.error(
                request,
                e.message,
                extra_tags="new-single-invoice",
            )
            return render(
                request,
                "invoices/single_invoice.html",
                {
                    "invoice_form": invoice_form,
                    "line_item_forms": format_line_items(request),
                },
            )
        if not invoice_form.is_valid():
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
        if invoice_status := request.GET.get("status"):
            if invoice_status == "draft":
                saved_single_invoice.status = SingleInvoice.InvoiceStatus.DRAFT
            elif invoice_status == "send":
                saved_single_invoice.status = SingleInvoice.InvoiceStatus.SENT
        saved_single_invoice.save()

        # Save line items to the invoice if valid
        for line_form in format_line_items(request):
            if line_form.is_valid():
                line_item_saved = line_form.save(commit=False)
                line_item_saved.invoice = saved_single_invoice
                line_item_saved.save()
        saved_single_invoice.update()
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

    raise Http404()


@login_required()
@require_http_methods(["GET", "POST", "DELETE"])
def update_single_invoice(request, single_invoice_id):
    single_invoice_obj = get_object_or_404(SingleInvoice, id=single_invoice_id)
    invoice_form = SingleInvoiceForm(request.POST or None, instance=single_invoice_obj)
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
        # Check that invoice has at least 1 line item before proceeding
        try:
            validate_line_items(request)
        except ValidationError as e:
            messages.error(
                request,
                e.message,
                extra_tags="update-single-invoice",
            )
            return render(
                request,
                "invoices/single_invoice.html",
                {
                    "single_invoice": single_invoice_obj,
                    "invoice_form": invoice_form,
                    "line_item_forms": format_line_items(request),
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
            for line_form in format_line_items(request):
                if line_form.is_valid():
                    line_item_saved = line_form.save(commit=False)
                    line_item_saved.invoice = saved_single_invoice
                    line_item_saved.save()

            saved_single_invoice.update_total_price()
            if saved_single_invoice.status == SingleInvoice.InvoiceStatus.SENT:
                saved_single_invoice.send_invoice()
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
