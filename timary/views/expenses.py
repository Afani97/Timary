from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from timary.forms import ExpensesForm
from timary.models import Expenses, InvoiceManager
from timary.utils import show_alert_message


@login_required()
@require_http_methods(["GET", "POST"])
def get_expenses(request, invoice_id):
    invoice = InvoiceManager(invoice_id).invoice
    if invoice.user != request.user:
        raise Http404

    expense_forms = [ExpensesForm(instance=exp) for exp in invoice.expenses.all()]
    return render(
        request,
        "expenses/list.html",
        {
            "new_expense_form": ExpensesForm(),
            "expense_forms": expense_forms,
            "invoice": invoice,
        },
    )


@login_required()
@require_http_methods(["GET", "POST"])
def create_expenses(request, invoice_id):
    invoice = InvoiceManager(invoice_id).invoice
    if invoice.user != request.user:
        raise Http404
    expense_form = ExpensesForm(request.POST or None)
    if request.method == "POST":
        if expense_form.is_valid():
            expense_saved = expense_form.save(commit=False)
            expense_saved.invoice = invoice
            expense_saved.date_tracked = timezone.now()
            expense_saved.save()
            response = render(
                request,
                "partials/_expense.html",
                {"expense": expense_saved, "form": expense_form},
            )
            show_alert_message(
                response, "success", "New expense added!", "clearExpensesModal"
            )
            return response

    response = render(request, "expenses/_form.html", {"form": expense_form})
    response["HX-Retarget"] = "#new-hours-form"
    return response


@login_required()
@require_http_methods(["GET", "POST"])
def update_expenses(request, expenses_id):
    expense_obj = Expenses.objects.get(id=expenses_id)
    if expense_obj.invoice.user != request.user:
        raise Http404
    expense_form = ExpensesForm(request.POST or None, instance=expense_obj)
    if request.method == "POST":
        if expense_form.is_valid():
            expense_saved = expense_form.save(commit=False)
            expense_saved.invoice = expense_obj.invoice
            expense_saved.date_tracked = timezone.now()
            expense_saved.save()
            response = render(
                request,
                "partials/_expense.html",
                {
                    "expense": expense_saved,
                    "form": ExpensesForm(instance=expense_saved),
                },
            )
            show_alert_message(response, "success", "Expense updated!")
            return response

    response = render(
        request,
        "partials/_expense.html",
        {"form": expense_form, "expense": expense_obj},
    )
    response["HX-Retarget"] = f"#expenses-form-{expense_obj.slug_id}"
    return response


@login_required()
@require_http_methods(["DELETE"])
def delete_expenses(request, expenses_id):
    expense_obj = Expenses.objects.get(id=expenses_id)
    if expense_obj.invoice.user != request.user:
        raise Http404
    expense_obj.delete()

    response = HttpResponse(status=200)
    show_alert_message(response, "success", "Expenses deleted")
    return response
