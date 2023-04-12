import datetime

from dateutil.relativedelta import relativedelta
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.html import format_html
from django.views.decorators.http import require_http_methods

from timary.forms import HoursLineItemForm
from timary.hours_manager import HoursManager
from timary.models import SentInvoice, User
from timary.utils import Calendar, get_users_localtime, show_active_timer


def bad_request(request, exception):
    return redirect(reverse("timary:landing_page"))


def get_pending_sent_invoices(user):
    sent_invoices_pending = SentInvoice.objects.filter(user=user).exclude(
        Q(paid_status=SentInvoice.PaidStatus.PAID)
        | Q(paid_status=SentInvoice.PaidStatus.CANCELLED)
    )
    balance_owed = sent_invoices_pending.aggregate(owed=Sum("total_price"))
    return {
        "pending_invoices": {
            "num_pending": sent_invoices_pending.count(),
            "balance": balance_owed["owed"] or 0,
        }
    }


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
        "last_month_date": datetime.date.today() - relativedelta(months=1),
    }

    if len(show_most_frequent_options) > 0:
        context["frequent_options"] = show_most_frequent_options
    context.update(show_active_timer(user))
    context.update(hours_manager.get_hours_tracked())
    context.update(get_pending_sent_invoices(request.user))
    return render(request, "timary/index.html", context=context)


@login_required()
@require_http_methods(["GET"])
def dashboard_stats(request):
    hours_manager = HoursManager(request.user)
    context = hours_manager.get_hours_tracked()
    context["new_hour_form"] = HoursLineItemForm(user=request.user)
    context.update(show_active_timer(request.user))
    context.update(get_pending_sent_invoices(request.user))
    response = render(
        request,
        "partials/_dashboard_stats.html",
        context,
    )
    response["HX-ResetTimer"] = "resetTimer"
    return response


@login_required()
@require_http_methods(["GET"])
def hours_for_month(request):
    """Show updated hours list for month"""
    request_month = request.GET.get("month")
    month_date = datetime.datetime.strptime(request_month, "%b. %d, %Y")
    hours_manager = HoursManager(request.user, month_date)
    context = {
        "hours": hours_manager.hours,
        "last_month_date": (month_date - relativedelta(months=1)).date(),
        "specific_month": month_date,
    }

    # Only show next month if it's less than current month, to prevent future dates appearing
    next_month = (month_date + relativedelta(months=1)).date()
    if next_month.replace(day=1) <= datetime.date.today().replace(day=1):
        context["next_month"] = next_month

    return render(request, "partials/_hours_inner_list.html", context)


@login_required()
@require_http_methods(["GET"])
def hours_calendar(request):
    today = get_users_localtime(request.user)
    cal = Calendar(request.user, today)
    html_cal = cal.formatmonth(withyear=True)
    return HttpResponse(format_html(html_cal))
