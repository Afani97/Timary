from crispy_forms.utils import render_crispy_form
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, QueryDict
from django.shortcuts import render
from django.template.context_processors import csrf
from django.views.decorators.http import require_http_methods

from timary.forms import SettingsForm, UserForm
from timary.utils import render_form_errors


@login_required()
@require_http_methods(["GET"])
def user_profile(request):
    tab = request.GET.get("tab", None)
    context = {
        "profile": request.user,
        "settings": request.user.settings,
        "sent_invoices": request.user.sent_invoices.order_by("-date_sent"),
        "archived_invoices": request.user.invoices.filter(is_archived=True),
    }
    if tab and 0 < int(tab) < 5:
        context["tab"] = tab
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
    html_form = render_crispy_form(profile_form, context=ctx)
    return HttpResponse(html_form)


@login_required()
@require_http_methods(["PUT"])
def update_user_profile(request):
    put_params = QueryDict(request.body)
    user_form = UserForm(put_params, instance=request.user, is_mobile=request.is_mobile)
    if user_form.is_valid():
        user = user_form.save()
        return render(request, "partials/_profile.html", {"user": user})

    ctx = {}
    ctx.update(csrf(request))
    user_form.helper.layout.insert(0, render_form_errors(user_form))
    html_form = render_crispy_form(user_form, context=ctx)
    return HttpResponse(html_form)
