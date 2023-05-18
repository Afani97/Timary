from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from timary.forms import UserForm
from timary.utils import show_active_timer, show_alert_message


@login_required()
@require_http_methods(["GET"])
def user_profile(request):
    context = {
        "profile": request.user,
        "settings": request.user.settings,
    }
    context.update(show_active_timer(request.user))
    return render(request, "timary/profile.html", context)


@login_required()
@require_http_methods(["GET"])
def profile_partial(request):
    return render(request, "partials/_profile.html", {"profile": request.user})


@login_required()
@require_http_methods(["GET"])
def edit_user_profile(request):
    profile_form = UserForm(instance=request.user)
    return render(request, "profile/_update.html", {"form": profile_form})


@login_required()
@require_http_methods(["POST"])
def update_user_profile(request):
    user_form = UserForm(request.POST, request.FILES, instance=request.user)
    if user_form.is_valid():
        user = user_form.save()
        if (
            not user.onboarding_tasks["add_phone_number"]
            and user.formatted_phone_number is not None
        ):
            user.onboarding_tasks["add_phone_number"] = True
            user.save()
        response = render(request, "partials/_profile.html", {"user": user})
        show_alert_message(
            response,
            "success",
            "Profile updated.",
        )
        return response
    else:
        return render(request, "profile/_update.html", {"form": user_form})
