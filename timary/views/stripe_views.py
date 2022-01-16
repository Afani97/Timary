import json

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from twilio.rest import Client

from timary.models import SentInvoice
from timary.services.stripe_service import StripeService


def invoice_payment_success(request, invoice_id):
    sent_invoice = get_object_or_404(SentInvoice, id=invoice_id)
    if sent_invoice.paid_status == SentInvoice.PaidStatus.PAID:
        return redirect(reverse("timary:login"))
    sent_invoice.paid_status = SentInvoice.PaidStatus.PAID
    sent_invoice.save()
    if sent_invoice.invoice.user.phone_number:
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        _ = client.messages.create(
            to=sent_invoice.invoice.user.formatted_phone_number,
            from_=settings.TWILIO_PHONE_NUMBER,
            body=f"Invoice for {sent_invoice.invoice.title} has been paid! "
            f"You should see {sent_invoice.total_price} deposited into your bank account shortly",
        )
    return render(request, "invoices/success_pay_invoice.html", {})


def onboard_success(request):
    stripe_client_secret = StripeService.create_payment_intent(request.user)
    return render(
        request,
        "auth/add-card-details.html",
        {
            "client_secret": stripe_client_secret,
            "stripe_public_key": settings.STRIPE_PUBLIC_API_KEY,
        },
    )


@csrf_exempt
def get_subscription_token(request):
    tokens = json.loads(request.body)

    first_token = tokens["first_token"]["id"]
    second_token = tokens["second_token"]["id"]
    success = StripeService.create_subscription(
        request.user, "starter", first_token, second_token
    )
    if success:
        return JsonResponse(
            {
                "redirect_url": request.build_absolute_uri(
                    reverse("timary:manage_invoices")
                )
            }
        )
    else:
        return JsonResponse({"error": "There was an error creating the subscription."})
