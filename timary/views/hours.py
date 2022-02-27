from crispy_forms.utils import render_crispy_form
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, QueryDict
from django.shortcuts import get_object_or_404, render
from django.template.context_processors import csrf
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from timary.forms import DailyHoursForm
from timary.models import DailyHoursInput


@login_required()
@require_http_methods(["POST"])
def create_daily_hours(request):
    hours_form = DailyHoursForm(request.POST)
    if hours_form.is_valid():
        hours = hours_form.save()
        response = render(request, "partials/_hour.html", {"hour": hours})
        response["HX-Trigger"] = "newHours"  # To trigger dashboard stats refresh
        response["HX-Trigger-After-Swap"] = "clearModal"  # To trigger modal closing
        return response
    context = {
        "form": hours_form,
        "url": "/hours/",
        "target": "#hours-list",
        "swap": "afterbegin",
        "btn_title": "Add new hours",
    }
    return render(request, "partials/_htmx_post_form.html", context, status=400)


@login_required()
@require_http_methods(["GET"])
def get_hours(request, hours_id):
    hours = get_object_or_404(DailyHoursInput, id=hours_id)
    if request.user != hours.invoice.user:
        raise Http404
    return render(request, "partials/_hour.html", {"hour": hours})


def render_hours_form(request, hour_instance, hour_form):
    context = {
        "form": hour_form,
        "url": reverse("timary:update_hours", kwargs={"hours_id": hour_instance.id}),
        "target": "this",
        "swap": "outerHTML",
        "cancel_url": reverse(
            "timary:get_single_hours", kwargs={"hours_id": hour_instance.id}
        ),
        "md_size": True,
        "btn_title": "Update hours",
    }
    return render(request, "partials/_htmx_put_form.html", context)


@login_required()
@require_http_methods(["GET"])
def edit_hours(request, hours_id):
    hours = get_object_or_404(DailyHoursInput, id=hours_id)
    if request.user != hours.invoice.user:
        raise Http404
    hours_form = DailyHoursForm(
        instance=hours, user=request.user, is_mobile=request.is_mobile
    )
    ctx = {}
    ctx.update(csrf(request))
    html_form = render_crispy_form(hours_form, context=ctx)
    print(html_form)
    # return
    return render_hours_form(request, hour_instance=hours, hour_form=hours_form)


@login_required()
@require_http_methods(["PUT"])
def update_hours(request, hours_id):
    hours = get_object_or_404(DailyHoursInput, id=hours_id)
    if request.user != hours.invoice.user:
        raise Http404
    put_params = QueryDict(request.body)
    hours_form = DailyHoursForm(put_params, instance=hours, user=request.user)
    if hours_form.is_valid():
        updated_hours = hours_form.save()
        response = render(request, "partials/_hour.html", {"hour": updated_hours})
        response["HX-Trigger"] = "newHours"  # To trigger dashboard stats refresh
        return response
    return render_hours_form(request, hour_instance=hours, hour_form=hours_form)


@login_required()
@require_http_methods(["DELETE"])
def delete_hours(request, hours_id):
    hours = get_object_or_404(DailyHoursInput, id=hours_id)
    if request.user != hours.invoice.user:
        raise Http404
    hours.delete()
    response = HttpResponse("", status=200)
    response["HX-Trigger"] = "newHours"  # To trigger dashboard stats refresh
    return response
