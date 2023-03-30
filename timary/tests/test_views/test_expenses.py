import uuid

from django.urls import reverse

from timary.models import Expenses
from timary.tests.factories import ExpenseFactory, IntervalInvoiceFactory, UserFactory
from timary.tests.test_views.basetest import BaseTest


class TestExpenses(BaseTest):
    def setUp(self) -> None:
        super().setUp()

        self.user = UserFactory()
        self.client.force_login(self.user)

    def test_create_expense(self):
        invoice = IntervalInvoiceFactory(user=self.user)
        self.client.post(
            reverse("timary:create_expenses", kwargs={"invoice_id": invoice.id}),
            {
                "description": "New expense",
                "cost": "500",
            },
        )
        self.assertEqual(invoice.expenses.count(), 1)
        self.assertIsNotNone(invoice.expenses.first().date_tracked)

    def test_create_expense_error(self):
        response = self.client.post(
            reverse("timary:create_expenses", kwargs={"invoice_id": uuid.uuid4()}),
            {
                "description": "New expense",
                "cost": "500",
            },
        )
        self.assertEqual(response.status_code, 302)  # 404 redirect
        self.assertEqual(Expenses.objects.count(), 0)

    def test_update_expense(self):
        expense = ExpenseFactory(invoice__user=self.user)
        self.client.post(
            reverse("timary:update_expenses", kwargs={"expenses_id": expense.id}),
            {
                "description": "New expense",
                "cost": "500",
            },
        )
        expense.refresh_from_db()
        self.assertEqual(expense.description, "New expense")

    def test_update_expense_error(self):
        expense = ExpenseFactory(invoice__user=self.user, cost=100)
        self.client.post(
            reverse("timary:update_expenses", kwargs={"expenses_id": expense.id}),
            {
                "description": "New expense",
                "cost": "abc123",
            },
        )
        expense.refresh_from_db()
        self.assertEqual(expense.cost, 100)

    def test_get_expenses(self):
        invoice = IntervalInvoiceFactory(user=self.user)
        ExpenseFactory(invoice=invoice, description="New expense", cost=100)
        response = self.client.get(
            reverse("timary:get_expenses", kwargs={"invoice_id": invoice.id})
        )
        self.assertInHTML(
            """
            <input type="text" name="description" value="New expense" placeholder="New item... - Equipment"
            class="input input-bordered border-2 text-lg w-full placeholder-gray-500" maxlength="500"
            required id="id_description">
            """,
            response.content.decode(),
        )
        self.assertInHTML(
            """
            <input type="number" name="cost" value="100.00" placeholder="125.00"
            class="input input-bordered border-2 text-lg w-full placeholder-gray-500" step="0.01"
             required id="id_cost">
            """,
            response.content.decode(),
        )

    def test_delete_expense(self):
        expense = ExpenseFactory(invoice__user=self.user, cost=100)
        response = self.client.delete(
            reverse("timary:delete_expenses", kwargs={"expenses_id": expense.id})
        )
        with self.assertRaises(Expenses.DoesNotExist):
            expense.refresh_from_db()

        self.assertIn("Expenses delete", str(response.headers["HX-Trigger"]))
