from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db.models import F, Sum
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from timary.forms import DailyHoursForm, QuestionsForm
from timary.models import DailyHoursInput
from timary.services.stripe_service import StripeService


def bad_request(request, exception):
    return redirect(reverse("timary:landing_page"))


def landing_page(request):
    if request.user.is_authenticated:
        return redirect(reverse("timary:index"))
    return render(request, "timary/landing_page.html", {})


def contract_builder(request):
    return render(request, "contract/builder.html", {})


def terms_page(request):
    return render(request, "company/terms.html", {})


def privacy_page(request):
    return render(request, "company/privacy.html", {})


@login_required()
@require_http_methods(["POST"])
def questions(request):
    questions_form = QuestionsForm(request.POST)
    if questions_form.is_valid():
        send_mail(
            f"{request.user.first_name} ({request.user.email}) asked a question",
            questions_form.cleaned_data.get("question", ""),
            None,
            recipient_list=["ari@usetimary.com"],
            fail_silently=False,
        )
        return HttpResponse("Your request has been sent. Thanks!")
    return HttpResponse(
        "Oops, something went wrong, please refresh the page and try again."
    )


def get_dashboard_stats(hours_tracked):
    total_hours_sum = hours_tracked.aggregate(total_hours=Sum("hours"))["total_hours"]
    total_amount_sum = hours_tracked.annotate(
        total_amount=F("hours") * F("invoice__hourly_rate")
    ).aggregate(total=Sum("total_amount"))["total"]

    stats = {
        "total_hours": total_hours_sum or 0,
        "total_amount": total_amount_sum or 0,
    }
    return stats


def get_hours_tracked(user):
    current_month = DailyHoursInput.all_hours.current_month(user)
    last_month = DailyHoursInput.all_hours.last_month(user)
    current_year = DailyHoursInput.all_hours.current_year(user)
    context = {
        "current_month": get_dashboard_stats(current_month),
        "last_month": get_dashboard_stats(last_month),
        "current_year": get_dashboard_stats(current_year),
    }
    return context


@login_required
@require_http_methods(["GET"])
def index(request):
    user = request.user
    if user.get_invoices.count() == 0:
        return redirect(reverse("timary:manage_invoices"))
    context = {
        "new_hours": DailyHoursForm(
            user=user, is_mobile=request.is_mobile, request_method="get"
        ),
        "hours": DailyHoursInput.all_hours.current_month(user),
    }
    context.update(get_hours_tracked(user))
    return render(request, "timary/index.html", context=context)


@login_required()
@require_http_methods(["GET"])
def dashboard_stats(request):
    return render(
        request,
        "partials/_dashboard_stats.html",
        get_hours_tracked(request.user),
    )


@login_required()
def close_account(request, error=None):
    context = {}
    if error:
        context.update(error)
    return render(request, "timary/close_account.html", context=context)


@login_required()
@require_http_methods(["POST"])
def confirm_close_account(request):
    user_password = request.POST.get("password")
    if not request.user.check_password(user_password):
        return close_account(request, {"error": "Incorrect password"})
    user = request.user
    logout(request)
    StripeService.close_stripe_account(user)
    user.delete()
    return redirect(reverse("timary:register"))
