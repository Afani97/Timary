import datetime

from crispy_forms.utils import render_crispy_form
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.db.models import F, Sum
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from timary.forms import ContractForm, DailyHoursForm, QuestionsForm
from timary.models import Contract, DailyHoursInput
from timary.services.email_service import EmailService
from timary.services.stripe_service import StripeService


def bad_request(request, exception):
    return redirect(reverse("timary:landing_page"))


def landing_page(request):
    if request.user.is_authenticated:
        return redirect(reverse("timary:index"))
    return render(request, "timary/landing_page.html", {})


def contract_builder(request):
    context = {"today": datetime.datetime.today()}
    if request.method == "POST":
        contract_form = ContractForm(request.POST)
        if contract_form.is_valid():
            msg_body = render_to_string(
                "contract/contract_pdf.html",
                {
                    "form": contract_form.cleaned_data,
                    "today": datetime.datetime.today(),
                },
            )
            EmailService.send_html(
                "Hey! Here is your contract by Timary. Good luck!",
                msg_body,
                [
                    contract_form.cleaned_data.get("email"),
                    contract_form.cleaned_data.get("client_email"),
                ],
            )
            Contract.objects.create(
                email=contract_form.cleaned_data.get("email"),
                name=f'{contract_form.cleaned_data.get("first_name")} {contract_form.cleaned_data.get("last_name")}',
            )
            return HttpResponse("Sent! Check your email")
    return render(request, "contract/builder.html", context)


def terms_page(request):
    return render(request, "company/terms.html", {})


def privacy_page(request):
    return render(request, "company/privacy.html", {})


@login_required()
@require_http_methods(["POST"])
def questions(request):
    questions_form = QuestionsForm(request.POST)
    if questions_form.is_valid():
        EmailService.send_plain(
            f"{request.user.first_name} ({request.user.email}) asked a question",
            questions_form.cleaned_data.get("question", ""),
            "ari@usetimary.com",
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
    hours = DailyHoursInput.all_hours.current_month(user)
    latest_date_tracked = (
        hours.order_by("-date_tracked").first().date_tracked
        if hours.order_by("-date_tracked").first()
        else None
    )
    show_repeat = False
    if latest_date_tracked and latest_date_tracked != datetime.date.today():
        show_repeat = True

    context = {
        "new_hour_form": render_crispy_form(
            DailyHoursForm(user=user, is_mobile=request.is_mobile, request_method="get")
        ),
        "hours": hours,
        "show_repeat": show_repeat,
    }
    context.update(get_hours_tracked(user))
    return render(request, "timary/index.html", context=context)


@login_required()
@require_http_methods(["GET"])
def dashboard_stats(request):
    context = get_hours_tracked(request.user)
    context["new_hour_form"] = render_crispy_form(
        DailyHoursForm(
            user=request.user, is_mobile=request.is_mobile, request_method="get"
        )
    )
    response = render(
        request,
        "partials/_dashboard_stats.html",
        context,
    )
    response["HX-ResetTimer"] = "resetTimer"
    return response


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
