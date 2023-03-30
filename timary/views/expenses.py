from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from timary.forms import ExpensesForm
from timary.models import Expenses, InvoiceManager
from timary.utils import get_users_localtime, show_alert_message


@login_required()
@require_http_methods(["GET", "POST"])
def get_expenses(request, invoice_id):
    invoice = InvoiceManager(invoice_id).invoice
    if invoice.user != request.user:
        raise Http404

    expense_forms = [
        ExpensesForm(instance=exp)
        for exp in invoice.expenses.all().order_by("-date_tracked")
    ]
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
            if not expense_form.cleaned_data.get("date_tracked"):
                expense_saved.date_tracked = get_users_localtime(request.user)
            expense_saved.save()
            response = render(
                request,
                "partials/_expense.html",
                {
                    "expense": expense_saved,
                    "form": ExpensesForm(instance=expense_saved),
                },
            )
            show_alert_message(
                response, "success", "New expense added!", "clearExpensesModal"
            )
            return response
        else:
            response = render(
                request,
                "expenses/_form.html",
                {"form": expense_form, "invoice": invoice},
            )
            response["HX-Reswap"] = "outerHTML"
            show_alert_message(response, "warning", "Unable to create expense")
            return response

    response = render(
        request, "expenses/_form.html", {"form": expense_form, "invoice": invoice}
    )
    return response


@login_required()
@require_http_methods(["GET", "POST"])
def update_expenses(request, expenses_id):
    expense_obj = get_object_or_404(Expenses, id=expenses_id)
    if expense_obj.invoice.user != request.user:
        raise Http404
    expense_form = ExpensesForm(request.POST or None, instance=expense_obj)
    if request.method == "POST":
        if expense_form.is_valid():
            expense_saved = expense_form.save(commit=False)
            expense_saved.invoice = expense_obj.invoice
            if not expense_form.cleaned_data.get("date_tracked"):
                expense_saved.date_tracked = get_users_localtime(request.user)
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
        else:
            response = render(
                request,
                "partials/_expense.html",
                {"form": expense_form, "expense": expense_obj},
            )
            show_alert_message(response, "warning", "Unable to update expense")
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
    expense_obj = get_object_or_404(Expenses, id=expenses_id)
    if expense_obj.invoice.user != request.user:
        raise Http404
    expense_obj.delete()

    response = HttpResponse(status=200)
    show_alert_message(response, "success", "Expenses deleted")
    return response
