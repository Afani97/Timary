import datetime

from dateutil.relativedelta import relativedelta
from django.urls import reverse

from timary.tests.factories import DailyHoursFactory, UserFactory
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

        rendered_template = self.setup_template(
            "partials/_dashboard_stats.html",
            get_hours_tracked(self.user),
        )
        self.assertHTMLEqual(rendered_template, response.content.decode("utf-8"))
        self.assertEqual(response.status_code, 200)
