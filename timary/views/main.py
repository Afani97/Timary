from django.contrib.auth.decorators import login_required
from django.db.models import F, Sum
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django_q.tasks import async_task

from timary.forms import DailyHoursForm
from timary.models import DailyHoursInput


def get_dashboard_stats(user, hours_tracked=None):
    if not hours_tracked:
        hours_tracked = get_hours_tracked(user.userprofile)

    total_hours_sum = hours_tracked.aggregate(total_hours=Sum("hours"))["total_hours"]
    total_amount_sum = hours_tracked.annotate(
        total_amount=F("hours") * F("invoice__hourly_rate")
    ).aggregate(total=Sum("total_amount"))["total"]

    dashboard = {
        "total_hours": total_hours_sum or 0,
        "total_amount": total_amount_sum or 0,
    }
    return dashboard


def get_hours_tracked(userprofile):
    return (
        DailyHoursInput.objects.filter(invoice__user=userprofile)
        .select_related("invoice")
        .order_by("-date_tracked")
    )


@login_required
@require_http_methods(["GET"])
def index(request):
    user = request.user
    hours_tracked = get_hours_tracked(user.userprofile)

    context = {
        "new_hours": DailyHoursForm(userprofile=user.userprofile),
        "hours": hours_tracked,
        "dashboard": get_dashboard_stats(user, hours_tracked=hours_tracked),
    }
    return render(request, "timary/index.html", context=context)


@login_required()
@require_http_methods(["GET"])
def dashboard_stats(request):
    return render(
        request,
        "partials/_dashboard_stats.html",
        {"dashboard": get_dashboard_stats(request.user)},
    )


@login_required()
@require_http_methods(["GET"])
def test_async(request):
    async_task("timary.tasks.gather_invoices")
    return HttpResponse(status=204)
