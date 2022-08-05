from crispy_forms.utils import render_crispy_form
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django.template.context_processors import csrf
from django.views.decorators.http import require_http_methods

from timary.forms import UserForm
from timary.utils import add_loader, render_form_errors, show_alert_message


@login_required()
@require_http_methods(["GET"])
def user_profile(request):
    context = {
        "profile": request.user,
        "settings": request.user.settings,
    }
    return render(request, "timary/profile.html", context)


@login_required()
@require_http_methods(["GET"])
def profile_partial(request):
    return render(request, "partials/_profile.html", {"profile": request.user})


@login_required()
@require_http_methods(["GET"])
def edit_user_profile(request):
    profile_form = UserForm(instance=request.user, is_mobile=request.is_mobile)
    ctx = {}
    ctx.update(csrf(request))
    profile_form.helper.layout.insert(0, render_form_errors(profile_form))
    html_form = add_loader(render_crispy_form(profile_form, context=ctx))
    return HttpResponse(html_form)


@login_required()
@require_http_methods(["POST"])
def update_user_profile(request):
    user_form = UserForm(
        request.POST, request.FILES, instance=request.user, is_mobile=request.is_mobile
    )
    if user_form.is_valid():
        user = user_form.save()
        response = render(request, "partials/_profile.html", {"user": user})
        show_alert_message(
            response,
            "success",
            "Profile updated.",
        )
        return response

    ctx = {}
    ctx.update(csrf(request))
    user_form.helper.layout.insert(0, render_form_errors(user_form))
    html_form = add_loader(render_crispy_form(user_form, context=ctx))
    return HttpResponse(html_form)
