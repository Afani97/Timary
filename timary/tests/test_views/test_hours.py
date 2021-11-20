import datetime
import random
import uuid

from django.urls import reverse
from django.utils.http import urlencode

from timary.models import DailyHoursInput
from timary.tests.factories import (
    DailyHoursFactory,
    InvoiceFactory,
    UserProfilesFactory,
)
from timary.tests.test_views.basetest import BaseTest


class TestDailyHours(BaseTest):
    def setUp(self) -> None:
        super().setUp()

        self.user = UserProfilesFactory()
        self.client.force_login(self.user.user)
        self.hours_1 = DailyHoursFactory()

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
        self.assertEqual(response.status_code, 404)

    def test_get_hours(self):
        rendered_template = self.setup_template(
            "partials/_hour.html", {"hour": self.hours_1}
        )
        response = self.client.get(
            reverse("timary:get_single_hours", kwargs={"hours_id": self.hours_1.id})
        )
        self.assertHTMLEqual(rendered_template, response.content.decode("utf-8"))

    def test_get_hours_error(self):
        response = self.client.get(
            reverse("timary:get_single_hours", kwargs={"hours_id": uuid.uuid4()})
        )
        self.assertEqual(response.status_code, 404)

    def test_edit_daily_hours(self):
        hours = DailyHoursFactory(invoice__user=self.user)
        response = self.client.get(
            reverse("timary:edit_hours", kwargs={"hours_id": hours.id}),
        )
        self.assertContains(
            response,
            f'<option value="{hours.invoice.id}" selected>{hours.invoice.title}</option>',
        )
        self.assertEqual(response.templates[0].name, "partials/_htmx_put_form.html")
        self.assertEqual(response.status_code, 200)

    def test_edit_daily_hours_error(self):
        response = self.client.get(
            reverse("timary:edit_hours", kwargs={"hours_id": uuid.uuid4()}),
            data={},
        )
        self.assertEqual(response.status_code, 404)

    def test_update_daily_hours(self):
        hours = DailyHoursFactory()
        url_params = {
            "hours": random.randint(1, 23),
            "date_tracked": datetime.date.today() - datetime.timedelta(days=1),
            "invoice": str(hours.invoice.id),
        }
        response = self.client.put(
            reverse("timary:update_hours", kwargs={"hours_id": hours.id}),
            data=urlencode(url_params),  # HTML PUT FORM
        )
        hours.refresh_from_db()
        self.assertContains(
            response,
            f'<h2 class="card-title">{int(hours.hours)} hrs on {hours.date_tracked.strftime("%b. %d, %Y")}</h2>',
        )
        self.assertEqual(response.templates[0].name, "partials/_hour.html")
        self.assertEqual(response.status_code, 200)

    def test_update_daily_hours_error(self):
        response = self.client.put(
            reverse("timary:update_hours", kwargs={"hours_id": uuid.uuid4()}),
            data={},
        )
        self.assertEqual(response.status_code, 404)

    def test_delete_daily_hours(self):
        hours = DailyHoursFactory()
        response = self.client.delete(
            reverse("timary:delete_hours", kwargs={"hours_id": hours.id})
        )
        self.assertEqual(response.status_code, 200)

    def test_delete_daily_hours_error(self):
        response = self.client.delete(
            reverse("timary:delete_hours", kwargs={"hours_id": uuid.uuid4()}),
            data={},
        )
        self.assertEqual(response.status_code, 404)
