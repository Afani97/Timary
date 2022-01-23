from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, JsonResponse, QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from timary.forms import InvoiceForm, PayInvoiceForm
from timary.models import Invoice, SentInvoice, User
from timary.services.stripe_service import StripeService


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
    user: User = request.user
    invoice_form = InvoiceForm(request.POST)
    if invoice_form.is_valid():
        prev_invoice_count = Invoice.objects.filter(user=user).count()
        invoice = invoice_form.save(commit=False)
        invoice.user = user
        invoice.calculate_next_date()
        invoice.save()
        response = render(request, "partials/_invoice.html", {"invoice": invoice})
        response["HX-Trigger-After-Swap"] = "clearModal"  # To trigger modal closing
        response["HX-Trigger"] = "newInvoice"  # To trigger button refresh
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


@require_http_methods(["GET", "POST"])
@csrf_exempt
def pay_invoice(request, sent_invoice_id):
    sent_invoice = get_object_or_404(SentInvoice, id=sent_invoice_id)
    if sent_invoice.paid_status == SentInvoice.PaidStatus.PAID:
        return redirect(reverse("timary:login"))

    if request.method == "POST":
        pay_invoice_form = PayInvoiceForm(request.POST, sent_invoice=sent_invoice)
        if pay_invoice_form.is_valid():
            return JsonResponse({"valid": True, "errors": {}})
        else:
            return JsonResponse(
                {"valid": False, "errors": pay_invoice_form.errors.as_json()}
            )
    else:
        client_secret = StripeService.create_payment_intent_for_payout(sent_invoice)

        context = {
            "invoice": sent_invoice.invoice,
            "sent_invoice": sent_invoice,
            "hours_tracked": sent_invoice.get_hours_tracked(),
            "pay_invoice_form": PayInvoiceForm(),
            "stripe_public_key": StripeService.stripe_public_api_key,
            "client_secret": client_secret,
            "return_url": request.build_absolute_uri(
                reverse(
                    "timary:invoice_payment_success",
                    kwargs={"invoice_id": sent_invoice.id},
                )
            ),
        }
        return render(request, "invoices/pay_invoice.html", context)


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
    else:
        response["HX-Trigger"] = "newInvoice"  # To trigger button refresh
    return response


@login_required()
@require_http_methods(["GET"])
def create_invoice_partial(request):
    return render(request, "partials/_new_invoice_btn.html", {})
