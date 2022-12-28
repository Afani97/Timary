from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from timary.forms import DailyHoursForm
from timary.models import DailyHoursInput, User
from timary.querysets import HourStats
from timary.utils import show_active_timer


def bad_request(request, exception):
    return redirect(reverse("timary:landing_page"))


def get_hours_tracked(user):
    hour_stats = HourStats(user=user)
    context = {
        "current_month": hour_stats.get_current_month_stats(),
        "last_month": hour_stats.get_last_month_stats(),
        "current_year": hour_stats.get_this_year_stats(),
    }
    return context


@login_required
@require_http_methods(["GET"])
def index(request):
    user: User = request.user
    if user.get_invoices.count() == 0:
        return redirect(reverse("timary:manage_invoices"))
    hours = DailyHoursInput.all_hours.current_month(user)
    show_repeat_option = user.can_repeat_previous_hours_logged(hours)
    show_most_frequent_options = user.show_most_frequent_options(hours)

    context = {
        "new_hour_form": DailyHoursForm(user=user),
        "hours": hours,
        "show_repeat": show_repeat_option,
        "is_main_view": True,  # Needed to show timer controls, hidden for other views
    }
    if len(show_most_frequent_options) > 0:
        context["frequent_options"] = show_most_frequent_options
    context.update(show_active_timer(user))
    context.update(get_hours_tracked(user))
    return render(request, "timary/index.html", context=context)


@login_required()
@require_http_methods(["GET"])
def dashboard_stats(request):
    context = get_hours_tracked(request.user)
    context["new_hour_form"] = DailyHoursForm(user=request.user)
    context.update(show_active_timer(request.user))
    response = render(
        request,
        "partials/_dashboard_stats.html",
        context,
    )
    response["HX-ResetTimer"] = "resetTimer"
    return response
