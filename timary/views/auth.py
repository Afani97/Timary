from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse

from timary.forms import LoginForm, RegisterForm
from timary.models import UserProfile


def register_user(request):
    if request.user.is_authenticated:
        return redirect(reverse("timary:index"))
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            email = form.cleaned_data.get("email")
            user.username = email
            user.email = email
            user.first_name = form.cleaned_data.get("first_name")
            user.save()

            password = form.cleaned_data.get("password")
            authenticated_user = authenticate(username=user.username, password=password)
            if authenticated_user:
                user_profile = UserProfile(user=user)
                user_profile.save()
                login(request, authenticated_user)
                return redirect(reverse("timary:index"))
            else:
                form.add_error("email", "Unable to create account with credentials")
        else:
            return render(request, "auth/signup.html", {"form": form}, status=400)
    else:
        form = RegisterForm()
    return render(request, "auth/signup.html", {"form": form})


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
