from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from timary.models import SentInvoice


def invoice_payment_success(request, invoice_id):
    sent_invoice = get_object_or_404(SentInvoice, id=invoice_id)
    if sent_invoice.paid_status == SentInvoice.PaidStatus.PAID:
        return redirect(reverse("timary:login"))
    sent_invoice.paid_status = SentInvoice.PaidStatus.PAID
    sent_invoice.save()
    return render(request, "invoices/success_pay_invoice.html", {})
