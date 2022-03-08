from datetime import date, timedelta

from crispy_forms.utils import render_crispy_form
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.http import Http404, HttpResponse, QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.template.context_processors import csrf
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.timezone import localtime, now
from django.views.decorators.http import require_http_methods

from timary.forms import InvoiceForm
from timary.models import Invoice, SentInvoice
from timary.services.freshbook_service import FreshbookService
from timary.services.quickbook_service import QuickbookService


@login_required()
@require_http_methods(["GET"])
def manage_invoices(request):
    invoices = request.user.get_invoices.order_by("title")
    return render(
        request,
        "invoices/manage_invoices.html",
        {
            "invoices": invoices,
            "new_invoice": InvoiceForm(
                user=request.user, is_mobile=request.is_mobile, request_method="get"
            ),
            "upgrade_msg": request.user.upgrade_invoice_message,
        },
    )


@login_required()
@require_http_methods(["POST"])
def create_invoice(request):
    user = request.user
    invoice_form = InvoiceForm(
        request.POST,
        user=request.user,
        is_mobile=request.is_mobile,
        request_method="get",
    )
    if invoice_form.is_valid():
        prev_invoice_count = user.get_invoices.count()
        invoice = invoice_form.save(commit=False)
        invoice.user = user
        invoice.calculate_next_date()
        invoice.save()
        if user.quickbooks_realm_id:
            QuickbookService.create_customer(invoice)

        if user.freshbooks_account_id:
            FreshbookService.create_customer(invoice)
        response = render(request, "partials/_invoice.html", {"invoice": invoice})
        response["HX-Trigger-After-Swap"] = "clearModal"  # To trigger modal closing
        response["HX-Trigger"] = "newInvoice"  # To trigger button refresh
        if prev_invoice_count == 0:
            response[
                "HX-Redirect"
            ] = "/main/"  # To trigger refresh to remove empty state
        return response
    ctx = {}
    ctx.update(csrf(request))
    html_form = render_crispy_form(invoice_form, context=ctx)
    return HttpResponse(html_form, status=400)


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
        response["HX-Trigger"] = "newInvoice"  # To trigger button refresh
    return response


@login_required()
@require_http_methods(["GET"])
def edit_invoice(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    if request.user != invoice.user:
        raise Http404
    invoice_form = InvoiceForm(
        instance=invoice,
        user=request.user,
        is_mobile=request.is_mobile,
        request_method="put",
    )
    ctx = {}
    ctx.update(csrf(request))
    html_form = render_crispy_form(invoice_form, context=ctx)
    return HttpResponse(html_form)


@login_required()
@require_http_methods(["PUT"])
def update_invoice(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    if request.user != invoice.user:
        raise Http404
    put_params = QueryDict(request.body)
    invoice_form = InvoiceForm(
        put_params,
        instance=invoice,
        user=request.user,
        is_mobile=request.is_mobile,
        request_method="put",
    )
    if invoice_form.is_valid():
        invoice = invoice_form.save()
        if invoice.next_date:
            invoice.calculate_next_date(update_last=False)
        return render(request, "partials/_invoice.html", {"invoice": invoice})
    ctx = {}
    ctx.update(csrf(request))
    html_form = render_crispy_form(invoice_form, context=ctx)
    return HttpResponse(html_form)


@login_required()
@require_http_methods(["DELETE"])
def delete_invoice(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    if request.user != invoice.user:
        raise Http404
    invoice.delete()
    response = HttpResponse("", status=200)
    if request.user.get_invoices.count() == 0:
        response["HX-Refresh"] = "true"  # To trigger refresh to restore empty state
    else:
        response["HX-Trigger"] = "newInvoice"  # To trigger button refresh
    return response


@login_required()
@require_http_methods(["GET"])
def create_invoice_partial(request):
    context = {"upgrade_msg": request.user.upgrade_invoice_message}
    return render(request, "partials/_new_invoice_btn.html", context)


@login_required()
@require_http_methods(["GET"])
def resend_invoice_email(request, sent_invoice_id):
    sent_invoice = get_object_or_404(SentInvoice, id=sent_invoice_id)
    if sent_invoice.paid_status == SentInvoice.PaidStatus.PAID:
        return redirect(reverse("timary:user_profile"))
    invoice = sent_invoice.invoice
    if request.user != invoice.user:
        raise Http404
    today = localtime(now()).date()
    current_month = date.strftime(today, "%m/%Y")
    hours_tracked, total_amount = invoice.get_hours_stats(
        (sent_invoice.hours_start_date, sent_invoice.hours_end_date)
    )

    msg_subject = render_to_string(
        "email/invoice_subject.html",
        {"invoice": invoice, "current_month": current_month},
    ).strip()

    msg_body = render_to_string(
        "email/styled_email.html",
        {
            "can_accept_payments": invoice.user.can_accept_payments,
            "site_url": settings.SITE_URL,
            "user_name": invoice.user.first_name,
            "next_weeks_date": today + timedelta(weeks=1),
            "recipient_name": invoice.email_recipient_name,
            "total_amount": total_amount,
            "sent_invoice_id": sent_invoice.id,
            "invoice": invoice,
            "hours_tracked": hours_tracked,
            "todays_date": today,
        },
    )
    send_mail(
        msg_subject,
        None,
        None,
        recipient_list=[invoice.email_recipient],
        fail_silently=False,
        html_message=msg_body,
    )
    return render(
        request,
        "partials/_sent_invoice.html",
        {"sent_invoice": sent_invoice, "invoice_resent": True},
    )
