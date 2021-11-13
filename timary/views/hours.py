from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, QueryDict
from django.shortcuts import get_object_or_404, render
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
        return response
    else:
        raise Http404


@login_required()
@require_http_methods(["GET"])
def get_hours(request, hours_id):
    hours = get_object_or_404(DailyHoursInput, id=hours_id)
    return render(request, "partials/_hour.html", {"hour": hours})


@login_required()
@require_http_methods(["GET"])
def new_hours(request):
    return render(
        request,
        "hours/new_hours.html",
        {"new_hours": DailyHoursForm(userprofile=request.user.userprofile)},
    )


@login_required()
@require_http_methods(["GET"])
def edit_hours(request, hours_id):
    hours = get_object_or_404(DailyHoursInput, id=hours_id)
    return render(
        request,
        "hours/edit_hours.html",
        {
            "hour": hours,
            "edit_hours": DailyHoursForm(
                instance=hours, userprofile=request.user.userprofile
            ),
            "hours_target": f"#{hours.slug_id}",
        },
    )


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
    else:
        raise Http404


@login_required()
@require_http_methods(["DELETE"])
def delete_hours(request, hours_id):
    hours = get_object_or_404(DailyHoursInput, id=hours_id)
    hours.delete()
    response = HttpResponse("", status=204)
    response["HX-Trigger"] = "newHours"  # To trigger dashboard stats refresh
    return response
