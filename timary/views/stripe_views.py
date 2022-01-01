import json

import stripe
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from timary.models import SentInvoice

stripe.api_key = settings.STRIPE_SECRET_API_KEY


@require_http_methods(["POST"])
@csrf_exempt
def create_payment_intent(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
        invoice_id = data.get("invoice_id", None)
        if invoice_id:
            sent_invoice = get_object_or_404(SentInvoice, id=invoice_id)
            if sent_invoice.paid_status == SentInvoice.PaidStatus.PAID:
                return redirect(reverse("timary:login"))

            # Create a PaymentIntent with the order amount and currency
            intent = stripe.PaymentIntent.create(
                amount=sent_invoice.total_price * 100,
                currency="usd",
                automatic_payment_methods={
                    "enabled": True,
                },
            )
            return JsonResponse({"clientSecret": intent["client_secret"]})
    except Exception as e:
        return JsonResponse(data={"msg": str(e)}, status=403)


def invoice_payment_success(request, invoice_id):
    sent_invoice = get_object_or_404(SentInvoice, id=invoice_id)
    if sent_invoice.paid_status == SentInvoice.PaidStatus.PAID:
        return redirect(reverse("timary:login"))
    sent_invoice.paid_status = SentInvoice.PaidStatus.PAID
    sent_invoice.save()
    return render(request, "invoices/success_pay_invoice.html", {})
