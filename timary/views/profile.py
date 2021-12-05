from django.contrib.auth.decorators import login_required
from django.http import QueryDict
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from timary.forms import UserForm


@login_required()
@require_http_methods(["GET"])
def user_profile(request):
    return render(request, "timary/profile.html", {"profile": request.user})


@login_required()
@require_http_methods(["GET"])
def profile_partial(request):
    return render(request, "partials/_profile.html", {"profile": request.user})


def render_profile_form(request, profile_form=None):
    context = {
        "form": profile_form,
        "url": reverse("timary:update_user_profile"),
        "target": "this",
        "swap": "outerHTML",
        "id": "update-user-profile",
        "md_block": True,
        "cancel_url": reverse("timary:user_profile_partial"),
        "btn_title": "Update profile",
    }
    return render(request, "partials/_htmx_put_form.html", context)


@login_required()
@require_http_methods(["GET"])
def edit_user_profile(request):
    profile_form = UserForm(instance=request.user)
    return render_profile_form(request, profile_form)


@login_required()
@require_http_methods(["PUT"])
def update_user_profile(request):
    put_params = QueryDict(request.body)
    user_form = UserForm(put_params, instance=request.user)
    if user_form.is_valid():
        user = user_form.save()
        return render(request, "partials/_profile.html", {"user": user})
    return render_profile_form(request=request, profile_form=user_form)
