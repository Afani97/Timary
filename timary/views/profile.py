from django.contrib.auth.decorators import login_required
from django.http import QueryDict
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from timary.forms import UserForm
from timary.services.stripe_service import StripeService


@login_required()
@require_http_methods(["GET"])
def user_profile(request):
    context = {
        "profile": request.user,
        "sent_invoices": request.user.sent_invoices.order_by("-date_sent"),
    }
    return render(request, "timary/profile.html", context)


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
    current_membership_tier = request.user.membership_tier
    put_params = QueryDict(request.body)
    user_form = UserForm(put_params, instance=request.user)
    if user_form.is_valid():
        user = user_form.save()
        if user_form.cleaned_data.get("membership_tier") != current_membership_tier:
            StripeService.create_subscription(user, delete_current=True)
        return render(request, "partials/_profile.html", {"user": user})
    return render_profile_form(request=request, profile_form=user_form)
