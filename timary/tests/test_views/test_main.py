import datetime
from unittest.mock import patch

from crispy_forms.utils import render_crispy_form
from dateutil.relativedelta import relativedelta
from django.urls import reverse
from django.utils.http import urlencode

from timary.forms import DailyHoursForm
from timary.models import Invoice, User
from timary.tests.factories import DailyHoursFactory, InvoiceFactory, UserFactory
from timary.tests.test_views.basetest import BaseTest
from timary.views import get_hours_tracked


class TestMain(BaseTest):
    def setUp(self) -> None:
        super().setUp()

        self.user = UserFactory()
        self.client.force_login(self.user)

    def test_index(self):
        hours_today = DailyHoursFactory(invoice__user=self.user)
        hours_last_month = DailyHoursFactory(
            invoice__user=self.user,
            date_tracked=datetime.date.today() - relativedelta(months=1),
        )
        response = self.client.get(reverse("timary:index"))

        self.assertEqual(response.status_code, 200)
        hours_today_template = self.setup_template(
            "partials/_hour.html",
            {"hour": hours_today},
        )
        hours_last_month_template = self.setup_template(
            "partials/_hour.html",
            {"hour": hours_last_month},
        )
        self.assertInHTML(
            hours_today_template,
            response.content.decode("utf-8"),
        )
        with self.assertRaises(AssertionError):
            self.assertInHTML(
                hours_last_month_template, response.content.decode("utf-8")
            )

    def test_dashboard_stats(self):
        DailyHoursFactory(invoice__user=self.user)
        DailyHoursFactory(
            invoice__user=self.user,
            date_tracked=datetime.date.today() - relativedelta(months=1),
        )
        response = self.client.get(reverse("timary:dashboard_stats"))

        context = get_hours_tracked(self.user)
        context["new_hour_form"] = render_crispy_form(
            DailyHoursForm(user=self.user, is_mobile=False, request_method="get")
        )

        rendered_template = self.setup_template(
            "partials/_dashboard_stats.html",
            context,
        )
        self.assertHTMLEqual(rendered_template, response.content.decode("utf-8"))
        self.assertEqual(response.status_code, 200)

    @patch(
        "timary.services.stripe_service.StripeService.close_stripe_account",
        return_value=True,
    )
    def test_close_account(self, stripe_mock):
        user = UserFactory()
        invoice = InvoiceFactory(user=user)
        self.client.force_login(user)
        data = urlencode({"password": "Apple101!"})
        response = self.client.post(
            reverse("timary:confirm_close_account"),
            data,
            content_type="application/x-www-form-urlencoded",
        )
        self.assertEqual(response.status_code, 302)

        with self.assertRaises(User.DoesNotExist) as e:
            user.refresh_from_db()
            self.assertEqual(str(e.exception), "User matching query does not exist.")

        with self.assertRaises(Invoice.DoesNotExist) as e:
            invoice.refresh_from_db()
            self.assertEqual(str(e.exception), "Invoice matching query does not exist.")
