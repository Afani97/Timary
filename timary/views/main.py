from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from timary.forms import HoursLineItemForm
from timary.hours_manager import HoursManager
from timary.models import User
from timary.utils import show_active_timer


def bad_request(request, exception):
    return redirect(reverse("timary:landing_page"))


@login_required
@require_http_methods(["GET"])
def index(request):
    user: User = request.user
    hours_manager = HoursManager(user)
    show_repeat_option = hours_manager.can_repeat_previous_hours_logged()
    show_most_frequent_options = hours_manager.show_most_frequent_options()

    context = {
        "new_hour_form": HoursLineItemForm(user=user),
        "hours": hours_manager.hours,
        "show_repeat": show_repeat_option,
        "is_main_view": True,  # Needed to show timer controls, hidden for other views
    }
    if len(show_most_frequent_options) > 0:
        context["frequent_options"] = show_most_frequent_options
    context.update(show_active_timer(user))
    context.update(hours_manager.get_hours_tracked())
    return render(request, "timary/index.html", context=context)


@login_required()
@require_http_methods(["GET"])
def dashboard_stats(request):
    hours_manager = HoursManager(request.user)
    context = hours_manager.get_hours_tracked()
    context["new_hour_form"] = HoursLineItemForm(user=request.user)
    context.update(show_active_timer(request.user))
    response = render(
        request,
        "partials/_dashboard_stats.html",
        context,
    )
    response["HX-ResetTimer"] = "resetTimer"
    return response
