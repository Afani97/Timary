import datetime

from dateutil import relativedelta
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.db.models import F, Sum
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from timary.forms import ContractForm, DailyHoursForm, QuestionsForm
from timary.models import Contract, DailyHoursInput, SentInvoice
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
        total_amount=F("hours") * F("invoice__invoice_rate")
    ).aggregate(total=Sum("total_amount"))["total"]

    stats = {
        "total_hours": total_hours_sum or 0,
        "total_amount": total_amount_sum or 0,
    }
    return stats


class HourStats:
    def __init__(self, user):
        self.user = user
        self.current_month = datetime.datetime.today()
        self.last_month = datetime.datetime.today() - relativedelta.relativedelta(
            months=1
        )
        self.first_month = datetime.datetime.today().replace(month=1)

    def get_sent_invoices_stats(self, date_range=None):
        sent_invoices = SentInvoice.objects.filter(user=self.user)
        if date_range:
            sent_invoices = sent_invoices.filter(date_sent__range=date_range)
        else:
            sent_invoices = sent_invoices.filter(
                date_sent__month__gte=self.current_month.month,
                date_sent__year__gte=self.current_month.year,
            )
        print(sent_invoices)
        total_hours = 0
        total_amount = 0
        for sent_invoice in sent_invoices:
            hours, total = sent_invoice.get_hours_tracked()
            total_hours += hours.aggregate(total_hours=Sum("hours"))["total_hours"]
            total_amount += total

        return total_hours, total_amount

    def get_hour_stats(self, date_range=None):
        qs = (
            DailyHoursInput.objects.filter(
                invoice__user=self.user, invoice__is_archived=False
            )
            .exclude(hours=0)
            .select_related("invoice")
            .order_by("-date_tracked")
        )
        if date_range:
            qs = qs.filter(date_tracked__range=date_range)
        else:
            qs = qs.filter(
                date_tracked__month__gte=self.current_month.month,
                date_tracked__year__gte=self.current_month.year,
            )
        total_hours_sum = qs.aggregate(total_hours=Sum("hours"))["total_hours"]
        total_amount_sum = qs.annotate(
            total_amount=F("hours") * F("invoice__invoice_rate")
        ).aggregate(total=Sum("total_amount"))["total"]

        return total_hours_sum or 0, total_amount_sum or 0

    def get_current_month_stats(self):
        sent_invoice_stats = self.get_sent_invoices_stats()
        hour_stats = self.get_hour_stats()
        print(sent_invoice_stats)
        print(hour_stats)

    def get_last_month_stats(self):
        date_range = (self.last_month, self.current_month.replace(day=1))
        sent_invoice_stats = self.get_sent_invoices_stats(date_range)
        hour_stats = self.get_hour_stats(date_range)
        print(sent_invoice_stats)
        print(hour_stats)


def get_hours_tracked(user):
    HourStats(user).get_current_month_stats()
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
    show_repeat_option = user.can_repeat_previous_hours_logged(hours)

    context = {
        "new_hour_form": DailyHoursForm(user=user),
        "hours": hours,
        "show_repeat": show_repeat_option,
    }
    context.update(get_hours_tracked(user))
    return render(request, "timary/index.html", context=context)


@login_required()
@require_http_methods(["GET"])
def dashboard_stats(request):
    context = get_hours_tracked(request.user)
    context["new_hour_form"] = DailyHoursForm(user=request.user)
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
