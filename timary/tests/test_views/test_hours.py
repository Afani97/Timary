import datetime
import random

from django.urls import reverse
from django.utils.http import urlencode

from timary.models import DailyHoursInput
from timary.tests.factories import (
    DailyHoursFactory,
    InvoiceFactory,
    SentInvoiceFactory,
    UserFactory,
)
from timary.tests.test_views.basetest import BaseTest


class TestDailyHours(BaseTest):
    def setUp(self) -> None:
        super().setUp()

        self.user = UserFactory()
        self.client.force_login(self.user)
        self.hours = DailyHoursFactory(invoice__user=self.user)
        self.hours_no_user = DailyHoursFactory()

    def test_get_hours_not_invoiced_yet(self):
        sent_invoice = SentInvoiceFactory(invoice=self.hours.invoice)
        hours_invoiced = DailyHoursFactory(
            invoice=self.hours.invoice, sent_invoice_id=sent_invoice.id
        )

        response = self.client.get(reverse("timary:index"))

        self.assertEqual(response.status_code, 200)
        hours_invoiced_template = self.setup_template(
            "partials/_hour.html",
            {"hour": hours_invoiced},
        )
        self.assertNotIn('<div class="card-actions">', hours_invoiced_template)
        hours_not_invoiced_template = self.setup_template(
            "partials/_hour.html",
            {"hour": self.hours},
        )
        self.assertIn('<div class="card-actions">', hours_not_invoiced_template)

    def test_create_daily_hours(self):
        DailyHoursInput.objects.all().delete()
        invoice = InvoiceFactory(user=self.user)
        response = self.client.post(
            reverse("timary:create_hours"),
            data={
                "hours": 1,
                "date_tracked": datetime.date.today(),
                "invoice": invoice.id,
            },
        )
        self.assertEqual(response.status_code, 200)
        hours = [DailyHoursInput.objects.first()]
        rendered_template = self.setup_template(
            "partials/_hours_list.html", {"hours": hours, "show_repeat": False}
        )
        self.assertHTMLEqual(rendered_template, response.content.decode("utf-8"))

    def test_create_daily_hours_error(self):
        DailyHoursInput.objects.all().delete()
        invoice = InvoiceFactory(user=self.user)
        response = self.client.post(
            reverse("timary:create_hours"),
            data={
                "hours": -1,
                "date_tracked": datetime.date.today(),
                "invoice": invoice.id,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertInHTML(
            "Invalid hours logged. Please log between 0 and 24 hours",
            response.content.decode("utf-8"),
        )

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
            <h2 class="card-title">{self.hours.hours} hrs for {self.hours.invoice.title}</h2>
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

    def test_patch_daily_hours(self):
        random_hours = random.randint(1, 23)
        url_params = {
            "hours": random_hours,
            "date_tracked": datetime.date.today() - datetime.timedelta(days=1),
            "invoice": self.hours.invoice.id,
        }
        response = self.client.patch(
            reverse("timary:patch_hours", kwargs={"hours_id": self.hours.id}),
            data=urlencode(url_params),  # HTML PATCH FORM
        )
        self.hours.refresh_from_db()
        self.assertInHTML(
            f"""
            <input type="text" name="hours" value="{random_hours}" value="1.0"
            class="input input-bordered text-lg hours-input w-20 textinput textInput"
            required id="id_hours">
            """,
            response.content.decode("utf-8"),
        )
        self.assertEqual(response.templates[0].name, "partials/_form_success.html")
        self.assertEqual(response.status_code, 200)
        self.assertInHTML(
            '<li class="text-success text-center">Successfully updated hours</li>',
            response.content.decode("utf-8"),
        )

    def test_patch_daily_hours_error(self):
        response = self.client.patch(
            reverse("timary:patch_hours", kwargs={"hours_id": self.hours_no_user.id}),
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

    def test_repeat_daily_hours(self):
        DailyHoursInput.objects.all().delete()
        DailyHoursFactory(
            invoice=InvoiceFactory(user=self.user),
            date_tracked=datetime.date.today() - datetime.timedelta(days=1),
        )
        DailyHoursFactory(
            invoice=InvoiceFactory(user=self.user),
            date_tracked=datetime.date.today() - datetime.timedelta(days=1),
        )
        self.assertEqual(DailyHoursInput.objects.count(), 2)

        response = self.client.get(reverse("timary:repeat_hours"))
        self.assertEqual(response.status_code, 200)

        self.assertEqual(DailyHoursInput.objects.count(), 4)
        hours = DailyHoursInput.objects.filter(
            invoice__user=self.user, date_tracked=datetime.date.today()
        )
        rendered_template = self.setup_template(
            "partials/_hours_grid.html", {"hours": hours}
        )
        self.assertHTMLEqual(rendered_template, response.content.decode("utf-8"))
