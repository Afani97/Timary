from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, QueryDict
from django.shortcuts import get_object_or_404, render
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
        "btn_title": "Update hours",
    }
    return render(request, "partials/_htmx_put_form.html", context)


@login_required()
@require_http_methods(["GET"])
def edit_hours(request, hours_id):
    hours = get_object_or_404(DailyHoursInput, id=hours_id)
    hours_form = DailyHoursForm(instance=hours, userprofile=request.user.userprofile)
    return render_hours_form(request, hour_instance=hours, hour_form=hours_form)


@login_required()
@require_http_methods(["PUT"])
def update_hours(request, hours_id):
    hours = get_object_or_404(DailyHoursInput, id=hours_id)
    put_params = QueryDict(request.body)
    hours_form = DailyHoursForm(
        put_params, instance=hours, userprofile=request.user.userprofile
    )
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
    hours.delete()
    response = HttpResponse("", status=200)
    response["HX-Trigger"] = "newHours"  # To trigger dashboard stats refresh
    return response
