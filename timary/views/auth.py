from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse

from timary.forms import LoginForm, RegisterForm, RegisterSubscriptionForm
from timary.services.stripe_service import StripeService


# Remove, switching to register_subscription
def register_user(request):
    if request.user.is_authenticated:
        return redirect(reverse("timary:index"))
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
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
        request_data = request.POST.copy()
        first_token = request_data.pop("first_token")[0]
        second_token = request_data.pop("second_token")[0]
        form = RegisterSubscriptionForm(request.POST)
        if form.is_valid():
            user = form.save()
            password = form.cleaned_data.get("password")
            authenticated_user = authenticate(username=user.username, password=password)
            if authenticated_user:
                stripe_account_link_url = StripeService.create_new_account(
                    request, user, first_token, second_token
                )
                login(request, authenticated_user)
                return redirect(stripe_account_link_url)
            else:
                form.add_error("email", "Unable to create account with credentials")
        else:
            context = {
                "form": form,
                "client_secret": StripeService.create_payment_intent(),
                "stripe_public_key": StripeService.stripe_public_api_key,
            }
            return render(
                request, "auth/register-subscription.html", context, status=400
            )
    else:
        form = RegisterSubscriptionForm()
        context = {
            "form": form,
            "client_secret": StripeService.create_payment_intent(),
            "stripe_public_key": StripeService.stripe_public_api_key,
        }
    return render(request, "auth/register-subscription.html", context)


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
