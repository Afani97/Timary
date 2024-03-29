from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from stripe.error import InvalidRequestError

from timary.forms import LoginForm, RegisterForm
from timary.models import User
from timary.services.stripe_service import StripeService


def register_user(request):
    if request.user.is_authenticated:
        return redirect(reverse("timary:index"))
    form = RegisterForm()

    if request.method == "POST":
        request_data = request.POST.copy()
        form = RegisterForm(request_data)
        if "first_token" not in request.POST or "second_token" not in request.POST:
            form.add_error(
                None, "We're having trouble creating your account. Please try again"
            )
        else:
            first_token = request_data.pop("first_token")[0]
            second_token = request_data.pop("second_token")[0]
            referrer_id = request.GET.get("referrer_id")
            if form.is_valid():
                user = form.save(commit=False)
                password = form.cleaned_data.get("password")
                stripe_card_error = False
                try:
                    connect_id, customer_id = StripeService.create_new_account(
                        request, user, first_token, second_token
                    )
                except InvalidRequestError:
                    stripe_card_error = True
                    form.add_error(
                        "password",
                        "Card entered needs to be a debit card, so Stripe can process your invoices.",
                    )

                if not stripe_card_error:
                    user.stripe_connect_id = connect_id
                    user.stripe_customer_id = customer_id
                    user.save()
                    authenticated_user = authenticate(
                        username=user.username, password=password
                    )
                    if authenticated_user:
                        login(request, authenticated_user)
                        user.onboard_user()

                        if referrer_id:
                            user_referred_by = User.objects.get(referral_id=referrer_id)
                            if user_referred_by:
                                user.referrer_id = user_referred_by.referral_id
                                user.save()
                        return redirect(reverse("timary:manage_invoices"))
                    else:
                        form.add_error(
                            "email", "Unable to create account with credentials"
                        )

    context = {
        "form": form,
        "client_secret": StripeService.create_payment_intent(),
        "stripe_public_key": StripeService.stripe_public_api_key,
        "stripe_card_element_ui": StripeService.frontend_ui(),
    }
    if (
        "referrer_id" in request.GET
        and User.objects.filter(referrer_id=request.GET.get("referrer_id")).exists()
    ):
        context["referrer_id"] = request.GET.get("referrer_id")
    return render(request, "auth/register.html", context)


def login_user(request):
    if request.user.is_authenticated:
        return redirect(reverse("timary:index"))
    form = LoginForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            email = form.cleaned_data.get("email")
            password = form.cleaned_data.get("password")
            user = authenticate(username=email, password=password)
            if user:
                login(request, user)
                return redirect(reverse("timary:index"))
            else:
                form.add_error("email", "Unable to verify credentials")
        else:
            form.add_error("email", "Unable to verify credentials")

    return render(request, "auth/login.html", {"form": form})


@login_required
def logout_user(request):
    logout(request)
    return redirect(reverse("timary:index"))
