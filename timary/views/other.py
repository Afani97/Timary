import datetime
import random

from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.core.files.storage import FileSystemStorage
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from weasyprint import HTML

from timary.forms import ContractForm, QuestionsForm
from timary.models import Contract
from timary.services.email_service import EmailService
from timary.services.stripe_service import StripeService


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
            html = HTML(string=msg_body)
            html.write_pdf(target="/tmp/mypdf.pdf")

            fs = FileSystemStorage("/tmp")
            with fs.open("mypdf.pdf") as pdf:
                response = HttpResponse(pdf, content_type="application/pdf")
                response["Content-Disposition"] = 'attachment; filename="contract.pdf"'
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
            return response
        else:
            context["contract_form"] = contract_form
    return render(request, "contract/builder.html", context)


def invoice_generator(request):
    return render(
        request,
        "invoice_generator/builder.html",
        {"random_num": random.randint(111111, 999999)},
    )


def stopwatch(request):
    return render(request, "stopwatch.html", {})


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
