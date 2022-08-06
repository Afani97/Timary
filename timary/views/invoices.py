from datetime import date

from crispy_forms.utils import render_crispy_form
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.http import Http404, HttpResponse, QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.template.context_processors import csrf
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from timary.forms import DailyHoursForm, InvoiceForm
from timary.models import Invoice, SentInvoice, User
from timary.services.email_service import EmailService
from timary.tasks import send_invoice
from timary.utils import add_loader, render_form_errors, show_alert_message


@login_required()
@require_http_methods(["GET"])
def manage_invoices(request):
    invoices = request.user.get_invoices.order_by("title")
    sent_invoices_owed = request.user.sent_invoices.filter(
        Q(paid_status=SentInvoice.PaidStatus.PENDING)
        | Q(paid_status=SentInvoice.PaidStatus.FAILED)
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
    ctx = {}
    ctx.update(csrf(request))
    context = {
        "invoices": invoices,
        "new_invoice": add_loader(
            render_crispy_form(
                InvoiceForm(
                    user=request.user, is_mobile=request.is_mobile, request_method="get"
                ),
                context=ctx,
            )
        ),
        "upgrade_msg": request.user.upgrade_invoice_message,
        "sent_invoices_owed": int(sent_invoices_owed),
        "sent_invoices_earned": int(sent_invoices_paid),
        "archived_invoices": request.user.invoices.filter(is_archived=True),
    }
    return render(
        request,
        "invoices/manage_invoices.html",
        context,
    )


@login_required()
@require_http_methods(["POST"])
def create_invoice(request):
    user: User = request.user
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
    ctx = {}
    ctx.update(csrf(request))
    invoice_form.helper.layout.insert(0, render_form_errors(invoice_form))
    html_form = add_loader(render_crispy_form(invoice_form, context=ctx))
    response = HttpResponse(html_form)
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
    invoice_form = InvoiceForm(
        instance=invoice,
        user=request.user,
        is_mobile=request.is_mobile,
        request_method="put",
    )
    ctx = {}
    ctx.update(csrf(request))
    invoice_form.helper.layout.insert(0, render_form_errors(invoice_form))
    html_form = add_loader(render_crispy_form(invoice_form, context=ctx))
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
        response = render(request, "partials/_invoice.html", {"invoice": invoice})
        show_alert_message(response, "success", f"{invoice.title} was updated.")
        return response
    ctx = {}
    ctx.update(csrf(request))
    invoice_form.helper.layout.insert(0, render_form_errors(invoice_form))
    html_form = add_loader(render_crispy_form(invoice_form, context=ctx))
    return HttpResponse(html_form)


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
    if invoice.get_hours_tracked().count() != 0:
        send_invoice(invoice.id)
        invoice.refresh_from_db()

        response = render(request, "partials/_invoice.html", {"invoice": invoice})

        show_alert_message(
            response,
            "success",
            f"Invoice for {invoice.title} has been sent to {invoice.email_recipient_name}",
        )
        return response
    else:
        response = render(request, "partials/_invoice.html", {"invoice": invoice})
        show_alert_message(
            response,
            "info",
            f"{invoice.title} does not have hours logged yet to invoice",
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
    sent_invoices = SentInvoice.objects.filter(invoice=invoice).all()
    if sent_invoices:
        return render(
            request,
            "partials/_sent_invoices_list.html",
            {"sent_invoices": sent_invoices},
        )
    else:
        return HttpResponse(
            "Looks like you haven't generated an invoice yet, log hours to do so."
        )
