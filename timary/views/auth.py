import json
import time

import stripe
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt

from timary.forms import LoginForm, RegisterForm, RegisterSubscriptionForm


def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[-1].strip()
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


def register_user(request):
    if request.user.is_authenticated:
        return redirect(reverse("timary:index"))
    if request.method == "POST":
        stripe.api_key = settings.STRIPE_SECRET_API_KEY
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            stripe_customer = stripe.Customer.create(email=user.email)
            user.stripe_customer_id = stripe_customer["id"]
            user.save()
            password = form.cleaned_data.get("password")
            authenticated_user = authenticate(username=user.username, password=password)
            if authenticated_user:
                login(request, authenticated_user)
                return redirect(reverse("timary:index"))
            else:
                form.add_error("email", "Unable to create account with credentials")
        else:
            return render(request, "auth/register.html", {"form": form}, status=400)
    else:
        form = RegisterForm()
    return render(request, "auth/register.html", {"form": form})


def register_subscription(request):
    if request.user.is_authenticated:
        return redirect(reverse("timary:index"))
    if request.method == "POST":
        stripe.api_key = settings.STRIPE_SECRET_API_KEY
        form = RegisterSubscriptionForm(request.POST)
        if form.is_valid():
            user = form.save()
            password = form.cleaned_data.get("password")
            authenticated_user = authenticate(username=user.username, password=password)
            if authenticated_user:
                stripe_connect_account = stripe.Account.create(
                    country="US",
                    type="custom",
                    email=user.email,
                    capabilities={
                        "card_payments": {"requested": True},
                        "transfers": {"requested": True},
                    },
                    business_type="individual",
                    business_profile={"mcc": "1520", "url": "www.usetimary.com"},
                    tos_acceptance={
                        "date": int(time.time()),
                        "ip": get_client_ip(request),
                    },
                    individual={
                        "email": user.email,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                    },
                )
                stripe_customer = stripe.Customer.create(
                    email=user.email,
                    name=user.get_full_name(),
                    stripe_account=stripe_connect_account["id"],
                )
                user.stripe_customer_id = stripe_customer["id"]
                user.stripe_connect_id = stripe_connect_account["id"]
                user.save()
                account_link = stripe.AccountLink.create(
                    account=stripe_connect_account["id"],
                    refresh_url=f"{settings.SITE_URL}/reauth",
                    return_url=f"{settings.SITE_URL}/onboarding_success",
                    type="account_onboarding",
                    collect="currently_due",
                )
                login(request, authenticated_user)
                return redirect(account_link["url"])
            else:
                form.add_error("email", "Unable to create account with credentials")
        else:
            return render(
                request, "auth/register-subscription.html", {"form": form}, status=400
            )
    else:
        form = RegisterSubscriptionForm()
    return render(request, "auth/register-subscription.html", {"form": form})


def onboard_success(request):
    stripe.api_key = settings.STRIPE_SECRET_API_KEY
    intent = stripe.SetupIntent.create(
        payment_method_types=["card"],
        customer=request.user.stripe_customer_id,
        stripe_account=request.user.stripe_connect_id,
    )
    return render(
        request,
        "auth/add-card-details.html",
        {
            "client_secret": intent["client_secret"],
            "stripe_public_key": settings.STRIPE_PUBLIC_API_KEY,
        },
    )


@csrf_exempt
def get_subscription_token(request):
    stripe.api_key = settings.STRIPE_SECRET_API_KEY
    tokens = json.loads(request.body)

    first_token = tokens["first_token"]["id"]
    second_token = tokens["second_token"]["id"]

    stripe.Customer.create_source(
        request.user.stripe_customer_id,
        source=first_token,
        stripe_account=request.user.stripe_connect_id,
    )

    product = stripe.Product.create(
        name="Basic", stripe_account=request.user.stripe_connect_id
    )
    price = stripe.Price.create(
        unit_amount=19 * 100,
        currency="usd",
        recurring={"interval": "month"},
        product=product["id"],
        stripe_account=request.user.stripe_connect_id,
    )

    stripe.Subscription.create(
        customer=request.user.stripe_customer_id,
        items=[
            {"price": price["id"]},
        ],
        stripe_account=request.user.stripe_connect_id,
    )

    stripe.Account.create_external_account(
        request.user.stripe_connect_id,
        external_account=second_token,
    )
    return JsonResponse(
        {"redirect_url": request.build_absolute_uri(reverse("timary:manage_invoices"))}
    )


def login_user(request):
    if request.user.is_authenticated:
        return redirect(reverse("timary:index"))
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data.get("email")
            password = form.cleaned_data.get("password")
            user = authenticate(username=email, password=password)
            if user:
                login(request, user)
                return redirect(reverse("timary:index"))
            else:
                form.add_error("email", "Unable to verify credentials")
        return render(request, "auth/login.html", {"form": form}, status=400)
    else:
        form = LoginForm()
        return render(request, "auth/login.html", {"form": form})


@login_required
def logout_user(request):
    logout(request)
    return redirect(reverse("timary:index"))
