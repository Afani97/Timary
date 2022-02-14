import datetime
import random

from django.urls import reverse
from django.utils.http import urlencode

from timary.models import DailyHoursInput
from timary.tests.factories import DailyHoursFactory, InvoiceFactory, UserFactory
from timary.tests.test_views.basetest import BaseTest


class TestDailyHours(BaseTest):
    def setUp(self) -> None:
        super().setUp()

        self.user = UserFactory()
        self.client.force_login(self.user)
        self.hours = DailyHoursFactory(invoice__user=self.user)
        self.hours_no_user = DailyHoursFactory()

    def test_create_daily_hours(self):
        DailyHoursInput.objects.all().delete()
        invoice = InvoiceFactory()
        response = self.client.post(
            reverse("timary:create_hours"),
            data={
                "hours": 1,
                "date_tracked": datetime.date.today(),
                "invoice": invoice.id,
            },
        )
        hours = DailyHoursInput.objects.first()
        rendered_template = self.setup_template("partials/_hour.html", {"hour": hours})
        self.assertHTMLEqual(rendered_template, response.content.decode("utf-8"))
        self.assertEqual(response.status_code, 200)

    def test_create_daily_hours_error(self):
        response = self.client.post(
            reverse("timary:create_hours"),
            data={},
        )
        self.assertEqual(response.status_code, 400)

    def test_get_hours(self):
        rendered_template = self.setup_template(
            "partials/_hour.html", {"hour": self.hours}
        )
        response = self.client.get(
            reverse("timary:get_single_hours", kwargs={"hours_id": self.hours.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertHTMLEqual(rendered_template, response.content.decode("utf-8"))

    def test_get_hours_error(self):
        response = self.client.get(
            reverse(
                "timary:get_single_hours", kwargs={"hours_id": self.hours_no_user.id}
            )
        )
        self.assertEqual(response.status_code, 302)

    def test_edit_daily_hours(self):
        response = self.client.get(
            reverse("timary:edit_hours", kwargs={"hours_id": self.hours.id}),
        )
        self.assertInHTML(
            f'<option value="{self.hours.invoice.id}" selected>{self.hours.invoice.title}</option>',
            response.content.decode("utf-8"),
        )
        self.assertEqual(response.templates[0].name, "partials/_htmx_put_form.html")
        self.assertEqual(response.status_code, 200)

    def test_edit_daily_hours_error(self):
        response = self.client.get(
            reverse("timary:edit_hours", kwargs={"hours_id": self.hours_no_user.id}),
            data={},
        )
        self.assertEqual(response.status_code, 302)

    def test_update_daily_hours(self):
        url_params = {
            "hours": random.randint(1, 23),
            "date_tracked": datetime.date.today() - datetime.timedelta(days=1),
            "invoice": str(self.hours.invoice.id),
        }
        response = self.client.put(
            reverse("timary:update_hours", kwargs={"hours_id": self.hours.id}),
            data=urlencode(url_params),  # HTML PUT FORM
        )
        self.hours.refresh_from_db()
        self.assertInHTML(
            f"""
            <h2 class="card-title">{int(self.hours.hours)} hrs on
            {self.hours.date_tracked.strftime("%b. %-d, %Y")}</h2>
            """,
            response.content.decode("utf-8"),
        )
        self.assertEqual(response.templates[0].name, "partials/_hour.html")
        self.assertEqual(response.status_code, 200)

    def test_update_daily_hours_error(self):
        response = self.client.put(
            reverse("timary:update_hours", kwargs={"hours_id": self.hours_no_user.id}),
            data={},
        )
        self.assertEqual(response.status_code, 302)

    def test_delete_daily_hours(self):
        response = self.client.delete(
            reverse("timary:delete_hours", kwargs={"hours_id": self.hours.id})
        )
        self.assertEqual(response.status_code, 200)

    def test_delete_daily_hours_error(self):
        response = self.client.delete(
            reverse("timary:delete_hours", kwargs={"hours_id": self.hours_no_user.id}),
            data={},
        )
        self.assertEqual(response.status_code, 302)
