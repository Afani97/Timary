from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, QueryDict
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from timary.forms import InvoiceForm
from timary.models import Invoice


@login_required()
@require_http_methods(["GET"])
def manage_invoices(request):
    user = request.user
    invoices = user.userprofile.invoices.all()
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
        invoice = invoice_form.save(commit=False)
        invoice.user = user.userprofile
        invoice.calculate_next_date()
        invoice.save()
        return render(request, "partials/_invoice.html", {"invoice": invoice})
    else:
        raise Http404


@login_required()
@require_http_methods(["GET"])
def get_invoice(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    return render(request, "partials/_invoice.html", {"invoice": invoice})


@login_required()
@require_http_methods(["GET"])
def new_invoice(request):
    return render(request, "invoices/new_invoice.html", {"new_invoice": InvoiceForm()})


@login_required()
@require_http_methods(["GET"])
def edit_invoice(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    return render(
        request,
        "invoices/edit_invoice.html",
        {
            "invoice": invoice,
            "edit_invoice": InvoiceForm(instance=invoice),
            "invoice_target": f"#{invoice.slug_title}",
        },
    )


@login_required()
@require_http_methods(["PUT"])
def update_invoice(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    put_params = QueryDict(request.body)
    invoice_form = InvoiceForm(put_params, instance=invoice)
    if invoice_form.is_valid():
        invoice = invoice_form.save()
        invoice.calculate_next_date(update_last=False)
        return render(request, "partials/_invoice.html", {"invoice": invoice})
    else:
        raise Http404


@login_required()
@require_http_methods(["DELETE"])
def delete_invoice(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    invoice.delete()
    return HttpResponse("", status=200)
