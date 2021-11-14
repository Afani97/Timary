from django.contrib.auth.decorators import login_required
from django.http import QueryDict
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from timary.forms import UserProfileForm


@login_required()
@require_http_methods(["GET"])
def user_profile(request):
    userprofile = request.user.userprofile
    return render(request, "timary/profile.html", {"profile": userprofile})


@login_required()
@require_http_methods(["GET"])
def profile_partial(request):
    userprofile = request.user.userprofile
    return render(request, "partials/_profile.html", {"profile": userprofile})


def render_profile_form(request, profile_form=None):
    context = {
        "form": profile_form,
        "url": reverse("timary:update_user_profile"),
        "target": "this",
        "swap": "outerHTML",
        "id": "update-user-profile",
        "cancel_url": reverse("timary:user_profile_partial"),
        "btn_title": "Update profile",
    }
    return render(request, "partials/_htmx_put_form.html", context)


@login_required()
@require_http_methods(["GET"])
def edit_user_profile(request):
    userprofile = request.user.userprofile
    profile_form = UserProfileForm(instance=userprofile.user)
    return render_profile_form(request, profile_form)


@login_required()
@require_http_methods(["PUT"])
def update_user_profile(request):
    user = request.user
    put_params = QueryDict(request.body)
    profile_form = UserProfileForm(put_params, instance=user)
    if profile_form.is_valid():
        update_profile = profile_form.save()
        userprofile = update_profile.userprofile
        return render(request, "partials/_profile.html", {"profile": userprofile})
    return render_profile_form(request=request, profile_form=profile_form)
