from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, QueryDict
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from timary.forms import InvoiceForm
from timary.models import Invoice


@login_required()
@require_http_methods(["GET"])
def manage_invoices(request):
    invoices = request.user.invoices.all().order_by("title")
    return render(
        request,
        "invoices/manage_invoices.html",
        {"invoices": invoices, "new_invoice": InvoiceForm()},
    )


@login_required()
@require_http_methods(["POST"])
def create_invoice(request):
    user = request.user
    invoice_form = InvoiceForm(request.POST)
    if invoice_form.is_valid():
        prev_invoice_count = Invoice.objects.filter(user=user).count()
        invoice = invoice_form.save(commit=False)
        invoice.user = user
        invoice.calculate_next_date()
        invoice.save()
        response = render(request, "partials/_invoice.html", {"invoice": invoice})
        response["HX-Trigger-After-Swap"] = "clearModal"  # To trigger modal closing
        if prev_invoice_count == 0:
            response[
                "HX-Redirect"
            ] = "/main/"  # To trigger refresh to remove empty state
        return response
    context = {
        "form": invoice_form,
        "url": "/invoices/",
        "target": "#invoices-list",
        "swap": "beforeend",
        "btn_title": "Add new invoice",
    }
    return render(request, "partials/_htmx_post_form.html", context, status=400)


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
    if invoice.next_date:
        invoice.next_date = None
    else:
        invoice.calculate_next_date()
    invoice.save()
    return render(request, "partials/_invoice.html", {"invoice": invoice})


def render_invoices_form(request, invoice_instance, invoice_form):
    context = {
        "form": invoice_form,
        "url": reverse(
            "timary:update_invoice", kwargs={"invoice_id": invoice_instance.id}
        ),
        "target": "this",
        "swap": "outerHTML",
        "cancel_url": reverse(
            "timary:get_single_invoice", kwargs={"invoice_id": invoice_instance.id}
        ),
        "btn_title": "Update invoice",
    }
    return render(request, "partials/_htmx_put_form.html", context)


@login_required()
@require_http_methods(["GET"])
def edit_invoice(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    if request.user != invoice.user:
        raise Http404
    invoice_form = InvoiceForm(instance=invoice)
    return render_invoices_form(
        request, invoice_instance=invoice, invoice_form=invoice_form
    )


@login_required()
@require_http_methods(["PUT"])
def update_invoice(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    if request.user != invoice.user:
        raise Http404
    put_params = QueryDict(request.body)
    invoice_form = InvoiceForm(put_params, instance=invoice)
    if invoice_form.is_valid():
        invoice = invoice_form.save()
        if invoice.next_date:
            invoice.calculate_next_date(update_last=False)
        return render(request, "partials/_invoice.html", {"invoice": invoice})
    return render_invoices_form(
        request, invoice_instance=invoice, invoice_form=invoice_form
    )


@login_required()
@require_http_methods(["DELETE"])
def delete_invoice(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    if request.user != invoice.user:
        raise Http404
    invoice.delete()
    response = HttpResponse("", status=200)
    if Invoice.objects.filter(user=request.user).count() == 0:
        response["HX-Refresh"] = "true"  # To trigger refresh to restore empty state
    return response
