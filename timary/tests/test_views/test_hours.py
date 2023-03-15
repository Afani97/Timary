import random
import zoneinfo

from django.db.models import Sum
from django.template.defaultfilters import floatformat
from django.template.defaultfilters import time as template_time
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode

from timary.models import HoursLineItem
from timary.tests.factories import (
    HoursLineItemFactory,
    IntervalInvoiceFactory,
    SentInvoiceFactory,
    UserFactory,
)
from timary.tests.test_views.basetest import BaseTest
from timary.utils import (
    get_date_parsed,
    get_starting_week_from_date,
    get_users_localtime,
)


class TestHourLineItems(BaseTest):
    def setUp(self) -> None:
        super().setUp()

        self.user = UserFactory()
        self.client.force_login(self.user)
        self.hours = HoursLineItemFactory(invoice__user=self.user)
        self.hours_no_user = HoursLineItemFactory()

    def test_get_hours_not_invoiced_yet(self):
        sent_invoice = SentInvoiceFactory(invoice=self.hours.invoice)
        hours_invoiced = HoursLineItemFactory(
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
        self.assertIn(
            '<div class="card-actions flex flex-col space-y-2">',
            hours_not_invoiced_template,
        )

    def test_create_daily_hours(self):
        invoice = IntervalInvoiceFactory(user=self.user)
        response = self.client.post(
            reverse("timary:create_hours"),
            data={
                "quantity": 1,
                "date_tracked": timezone.now(),
                "invoice": invoice.id,
            },
        )
        self.assertEqual(response.status_code, 200)

    def test_create_multiple_daily_hours(self):
        HoursLineItem.objects.all().delete()
        invoice = IntervalInvoiceFactory(user=self.user)
        invoice2 = IntervalInvoiceFactory(user=self.user)
        response = self.client.post(
            reverse("timary:create_hours"),
            data={
                "quantity": 1,
                "date_tracked": timezone.now().astimezone(
                    tz=zoneinfo.ZoneInfo("America/New_York")
                ),
                "invoice": [invoice.id, invoice2.id],
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(HoursLineItem.objects.count(), 2)

    def test_create_daily_hours_error(self):
        HoursLineItem.objects.all().delete()
        invoice = IntervalInvoiceFactory(user=self.user)
        response = self.client.post(
            reverse("timary:create_hours"),
            data={
                "quantity": -1,
                "date_tracked": timezone.now(),
                "invoice": invoice.id,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertInHTML(
            "Invalid hours logged. Please log between 0 and 24 hours",
            response.content.decode("utf-8"),
        )

    def test_create_multiple_daily_hours_error(self):
        HoursLineItem.objects.all().delete()
        invoice = IntervalInvoiceFactory(user=self.user)
        invoice2 = IntervalInvoiceFactory(user=self.user)
        response = self.client.post(
            reverse("timary:create_hours"),
            data={
                "quantity": -1,
                "date_tracked": timezone.now(),
                "invoice": [invoice.id, invoice2.id],
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(HoursLineItem.objects.count(), 0)
        self.assertInHTML(
            "Invalid hours logged. Please log between 0 and 24 hours",
            response.content.decode("utf-8"),
        )

    def test_create_more_than_24_hours_error(self):
        invoice = IntervalInvoiceFactory(user=self.user)
        HoursLineItemFactory(invoice=invoice, quantity=20)
        response = self.client.post(
            reverse("timary:create_hours"),
            data={
                "quantity": 10,
                "date_tracked": timezone.now().astimezone(
                    tz=zoneinfo.ZoneInfo(self.user.timezone)
                ),
                "invoice": invoice.id,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertInHTML(
            "Too many hours logged for today",
            response.content.decode("utf-8"),
        )

    def test_create_quick_hours(self):
        invoice = IntervalInvoiceFactory(user=self.user)
        hours_ref_id = f"{1.0}_{invoice.email_id}"
        response = self.client.get(
            f"{reverse('timary:quick_hours')}?hours_ref_id={hours_ref_id}"
        )
        self.assertEqual(response.status_code, 200)

    def test_create_quick_hours_error(self):
        response = self.client.get(
            f"{reverse('timary:quick_hours')}?hours_ref_id=abc123"
        )
        self.assertEqual(response.status_code, 204)
        self.assertIn(
            "Error adding hours",
            response.headers["HX-Trigger"],
        )

    def test_create_more_than_24_quick_hours_error(self):
        invoice = IntervalInvoiceFactory(user=self.user)
        HoursLineItemFactory(invoice=invoice, quantity=20)
        hours_ref_id = f"{10.0}_{invoice.email_id}"
        response = self.client.get(
            f"{reverse('timary:quick_hours')}?hours_ref_id={hours_ref_id}"
        )
        self.assertEqual(response.status_code, 204)
        self.assertIn(
            "Unable to add hours",
            response.headers["HX-Trigger"],
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
            "quantity": random.randint(1, 23),
            "date_tracked": timezone.now() - timezone.timedelta(days=1),
            "invoice": str(self.hours.invoice.id),
        }
        response = self.client.put(
            reverse("timary:update_hours", kwargs={"hours_id": self.hours.id}),
            data=urlencode(url_params),  # HTML PUT FORM
        )
        self.hours.refresh_from_db()
        self.assertInHTML(
            f"""
            <h2 class="text-3xl font-bold">{floatformat(self.hours.quantity, 2)}</h2>
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
            "quantity": random_hours,
            "date_tracked": timezone.now() - timezone.timedelta(days=1),
            "invoice": self.hours.invoice.id,
        }
        response = self.client.patch(
            reverse("timary:patch_hours", kwargs={"hours_id": self.hours.id}),
            data=urlencode(url_params),  # HTML PATCH FORM
        )
        self.hours.refresh_from_db()
        self.assertTemplateUsed(response, "hours/_patch.html")
        self.assertEqual(response.status_code, 200)
        self.assertInHTML(
            '<li class="text-success text-center">Successfully updated hours!</li>',
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
        HoursLineItem.objects.all().delete()
        HoursLineItemFactory(
            invoice=IntervalInvoiceFactory(user=self.user),
            date_tracked=timezone.now() - timezone.timedelta(days=1),
        )
        HoursLineItemFactory(
            invoice=IntervalInvoiceFactory(user=self.user),
            date_tracked=timezone.now() - timezone.timedelta(days=1),
        )
        self.assertEqual(HoursLineItem.objects.count(), 2)

        response = self.client.get(reverse("timary:repeat_hours"))
        self.assertEqual(response.status_code, 200)

        self.assertEqual(HoursLineItem.objects.count(), 4)

    def test_repeat_daily_hours_for_next_day(self):
        HoursLineItem.objects.all().delete()
        HoursLineItemFactory(
            invoice=IntervalInvoiceFactory(user=self.user),
            date_tracked=(timezone.now() - timezone.timedelta(days=2)).astimezone(
                tz=zoneinfo.ZoneInfo("America/New_York")
            ),
        )
        HoursLineItemFactory(
            invoice=IntervalInvoiceFactory(user=self.user),
            date_tracked=(timezone.now() - timezone.timedelta(days=2)).astimezone(
                tz=zoneinfo.ZoneInfo("America/New_York")
            ),
        )
        self.assertEqual(HoursLineItem.objects.count(), 2)
        _from = (
            (timezone.now() - timezone.timedelta(days=2))
            .astimezone(tz=zoneinfo.ZoneInfo("America/New_York"))
            .strftime("%b. %-d, %Y")
        )
        _to = (
            (timezone.now() - timezone.timedelta(days=1))
            .astimezone(tz=zoneinfo.ZoneInfo("America/New_York"))
            .strftime("%b. %-d, %Y")
        )
        url_params = f"from={_from}&to={_to}"
        response = self.client.get(f'{reverse("timary:repeat_hours")}?{url_params}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(HoursLineItem.objects.count(), 4)
        self.assertIn(
            "New hours copied!",
            response.headers["HX-Trigger"],
        )

    def test_repeat_daily_hours_for_previous_day(self):
        HoursLineItem.objects.all().delete()
        HoursLineItemFactory(
            invoice=IntervalInvoiceFactory(user=self.user),
            date_tracked=(timezone.now() - timezone.timedelta(days=1)).astimezone(
                tz=zoneinfo.ZoneInfo("America/New_York")
            ),
        )
        HoursLineItemFactory(
            invoice=IntervalInvoiceFactory(user=self.user),
            date_tracked=(timezone.now() - timezone.timedelta(days=1)).astimezone(
                tz=zoneinfo.ZoneInfo("America/New_York")
            ),
        )
        self.assertEqual(HoursLineItem.objects.count(), 2)
        _from = (
            (timezone.now() - timezone.timedelta(days=1))
            .astimezone(tz=zoneinfo.ZoneInfo("America/New_York"))
            .strftime("%b. %-d, %Y")
        )
        _to = (
            (timezone.now() - timezone.timedelta(days=2))
            .astimezone(tz=zoneinfo.ZoneInfo("America/New_York"))
            .strftime("%b. %-d, %Y")
        )
        url_params = f"from={_from}&to={_to}"
        response = self.client.get(f'{reverse("timary:repeat_hours")}?{url_params}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(HoursLineItem.objects.count(), 4)
        self.assertIn(
            "New hours copied!",
            response.headers["HX-Trigger"],
        )

    def test_error_repeat_daily_hours_for_specific_day_missing_hours(self):
        HoursLineItem.objects.all().delete()
        HoursLineItemFactory(
            invoice=IntervalInvoiceFactory(user=self.user),
            date_tracked=timezone.now() - timezone.timedelta(days=2),
        )
        HoursLineItemFactory(
            invoice=IntervalInvoiceFactory(user=self.user),
            date_tracked=timezone.now() - timezone.timedelta(days=2),
        )
        self.assertEqual(HoursLineItem.objects.count(), 2)

        response = self.client.get(reverse("timary:repeat_hours"))
        self.assertEqual(response.status_code, 204)

        self.assertIn("Unable to repeat new hours", str(response.headers))

    def test_error_repeat_daily_hours_for_specific_day_previous_to_invoice_last_date(
        self,
    ):
        HoursLineItem.objects.all().delete()
        last_date = (timezone.now() - timezone.timedelta(days=1)).astimezone(
            tz=zoneinfo.ZoneInfo("America/New_York")
        )
        invoice = IntervalInvoiceFactory(last_date=last_date)
        HoursLineItemFactory(
            invoice=invoice,
            date_tracked=last_date,
        )
        HoursLineItemFactory(
            invoice=invoice,
            date_tracked=last_date,
        )
        self.assertEqual(HoursLineItem.objects.count(), 2)

        _from = (
            (timezone.now() - timezone.timedelta(days=1))
            .astimezone(tz=zoneinfo.ZoneInfo("America/New_York"))
            .strftime("%b. %-d, %Y")
        )
        _to = (
            (timezone.now() - timezone.timedelta(days=2))
            .astimezone(tz=zoneinfo.ZoneInfo("America/New_York"))
            .strftime("%b. %-d, %Y")
        )
        url_params = f"from={_from}&to={_to}"
        response = self.client.get(f'{reverse("timary:repeat_hours")}?{url_params}')
        self.assertEqual(response.status_code, 204)
        self.assertEqual(HoursLineItem.objects.count(), 2)
        self.assertIn(
            "Unable to repeat new hours",
            response.headers["HX-Trigger"],
        )

        self.assertIn("Unable to repeat new hours", str(response.headers))

    def test_repeat_daily_hours_excluding_skipped(self):
        HoursLineItem.objects.all().delete()
        HoursLineItemFactory(
            quantity=1,
            invoice=IntervalInvoiceFactory(user=self.user),
            date_tracked=timezone.now() - timezone.timedelta(days=1),
        )
        HoursLineItemFactory(
            quantity=0,
            invoice=IntervalInvoiceFactory(user=self.user),
            date_tracked=timezone.now() - timezone.timedelta(days=1),
        )
        HoursLineItemFactory(
            quantity=2,
            invoice=IntervalInvoiceFactory(user=self.user),
            date_tracked=timezone.now() - timezone.timedelta(days=1),
        )
        self.assertEqual(
            int(
                HoursLineItem.objects.aggregate(hours_sum=Sum("quantity"))["hours_sum"]
            ),
            3,
        )
        self.assertEqual(
            HoursLineItem.objects.count(),
            3,
        )

        response = self.client.get(reverse("timary:repeat_hours"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            int(
                HoursLineItem.objects.aggregate(hours_sum=Sum("quantity"))["hours_sum"]
            ),
            6,
        )
        # Only two are created because 0 hours are skipped
        self.assertEqual(
            HoursLineItem.objects.count(),
            5,
        )

    def test_repeat_hours_including_repeating(self):
        HoursLineItem.objects.all().delete()
        HoursLineItemFactory(
            invoice=IntervalInvoiceFactory(user=self.user),
            date_tracked=timezone.now() - timezone.timedelta(days=1),
        )
        HoursLineItemFactory(
            invoice=IntervalInvoiceFactory(user=self.user),
            date_tracked=timezone.now() - timezone.timedelta(days=1),
        )
        start_week = get_starting_week_from_date(timezone.now()).isoformat()
        HoursLineItemFactory(
            invoice=IntervalInvoiceFactory(user=self.user),
            date_tracked=timezone.now() - timezone.timedelta(days=1),
            recurring_logic={
                "type": "recurring",
                "interval": "b",
                "interval_days": [get_date_parsed(timezone.now().date())],
                "starting_week": start_week,
            },
        )
        self.assertEqual(HoursLineItem.objects.count(), 3)

        response = self.client.get(reverse("timary:repeat_hours"))
        self.assertEqual(response.status_code, 200)

        self.assertEqual(HoursLineItem.objects.count(), 6)

    def test_repeat_hours_including_repeating_not_including_hours_if_not_scheduled(
        self,
    ):
        HoursLineItem.objects.all().delete()
        HoursLineItemFactory(
            invoice=IntervalInvoiceFactory(user=self.user),
            date_tracked=timezone.now() - timezone.timedelta(days=1),
        )
        HoursLineItemFactory(
            invoice=IntervalInvoiceFactory(user=self.user),
            date_tracked=timezone.now() - timezone.timedelta(days=1),
        )
        start_week = get_starting_week_from_date(timezone.now()).isoformat()
        HoursLineItemFactory(
            invoice=IntervalInvoiceFactory(user=self.user),
            date_tracked=timezone.now() - timezone.timedelta(days=1),
            recurring_logic={
                "type": "recurring",
                "interval": "b",
                "interval_days": [get_date_parsed(timezone.now())],
                "starting_week": start_week,
            },
        )
        # Biweekly shouldn't be added since not correct week
        bi_weekly_start_week = get_starting_week_from_date(
            timezone.now() + timezone.timedelta(weeks=+1)
        ).isoformat()
        HoursLineItemFactory(
            invoice=IntervalInvoiceFactory(user=self.user),
            date_tracked=timezone.now() - timezone.timedelta(days=1),
            recurring_logic={
                "type": "recurring",
                "interval": "b",
                "interval_days": [get_date_parsed(timezone.now())],
                "starting_week": bi_weekly_start_week,
            },
        )
        self.assertEqual(HoursLineItem.objects.count(), 4)

        response = self.client.get(reverse("timary:repeat_hours"))
        self.assertEqual(response.status_code, 200)

        self.assertEqual(HoursLineItem.objects.count(), 7)

    def test_create_repeating_hours(self):
        HoursLineItem.objects.all().delete()
        invoice = IntervalInvoiceFactory(user=self.user)
        response = self.client.post(
            reverse("timary:create_hours"),
            data={
                "quantity": 1,
                "date_tracked": timezone.now().astimezone(
                    tz=zoneinfo.ZoneInfo("America/New_York")
                ),
                "invoice": invoice.id,
                "repeating": True,
                "repeat_end_date": timezone.now() + timezone.timedelta(weeks=1),
                "repeat_interval_schedule": "d",
            },
        )
        self.assertEqual(response.status_code, 200)
        hours = HoursLineItem.objects.first()
        self.assertIsNotNone(hours.recurring_logic)

    def test_create_multiple_repeating_hours(self):
        HoursLineItem.objects.all().delete()
        invoice = IntervalInvoiceFactory(user=self.user)
        invoice2 = IntervalInvoiceFactory(user=self.user)
        response = self.client.post(
            reverse("timary:create_hours"),
            data={
                "quantity": 1,
                "date_tracked": timezone.now().astimezone(
                    tz=zoneinfo.ZoneInfo("America/New_York")
                ),
                "invoice": [invoice.id, invoice2.id],
                "repeating": True,
                "repeat_end_date": timezone.now() + timezone.timedelta(weeks=1),
                "repeat_interval_schedule": "d",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(HoursLineItem.objects.count(), 2)
        hours = HoursLineItem.objects.first()
        self.assertIsNotNone(hours.recurring_logic)

    def test_create_repeating_hours_error(self):
        HoursLineItem.objects.all().delete()
        invoice = IntervalInvoiceFactory(user=self.user)
        response = self.client.post(
            reverse("timary:create_hours"),
            data={
                "quantity": 1,
                "date_tracked": timezone.now(),
                "invoice": invoice.id,
                "repeating": True,
                "repeat_end_date": timezone.now() - timezone.timedelta(weeks=1),
                "repeat_interval_schedule": "d",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(HoursLineItem.objects.first())

    def test_create_recurring_hours(self):
        HoursLineItem.objects.all().delete()
        invoice = IntervalInvoiceFactory(user=self.user)
        response = self.client.post(
            reverse("timary:create_hours"),
            data={
                "quantity": 1,
                "date_tracked": timezone.now().astimezone(
                    tz=zoneinfo.ZoneInfo("America/New_York")
                ),
                "invoice": invoice.id,
                "recurring": True,
                "repeat_interval_schedule": "d",
            },
        )
        self.assertEqual(response.status_code, 200)
        hours = HoursLineItem.objects.first()
        self.assertIsNotNone(hours.recurring_logic)

    def test_create_recurring_hours_error(self):
        HoursLineItem.objects.all().delete()
        invoice = IntervalInvoiceFactory(user=self.user)
        response = self.client.post(
            reverse("timary:create_hours"),
            data={
                "quantity": 1,
                "date_tracked": timezone.now().astimezone(
                    tz=zoneinfo.ZoneInfo("America/New_York")
                ),
                "invoice": invoice.id,
                "recurring": True,
                "repeat_interval_schedule": "m",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(HoursLineItem.objects.first())

    def test_get_hour_for_paused_invoice(self):
        user = UserFactory()
        invoice = IntervalInvoiceFactory(user=user, is_paused=True)
        hours = HoursLineItemFactory(invoice=invoice)
        self.client.force_login(user)
        response = self.client.get(
            reverse("timary:get_single_hours", kwargs={"hours_id": hours.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Unpause invoice to edit.", response.content.decode("utf-8"))

    def test_cannot_patch_hour_for_paused_invoice(self):
        invoice = IntervalInvoiceFactory(user=self.user, is_paused=True)
        hours = HoursLineItemFactory(invoice=invoice)
        random_hours = random.randint(1, 23)
        url_params = {
            "quantity": random_hours,
            "date_tracked": timezone.now() - timezone.timedelta(days=1),
            "invoice": invoice.id,
        }
        response = self.client.patch(
            reverse("timary:patch_hours", kwargs={"hours_id": hours.id}),
            data=urlencode(url_params),  # HTML PATCH FORM
        )
        self.hours.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Unable to edit these hours since the invoice is paused.",
            str(response.headers),
        )

    def test_get_hours_ny_timezone(self):
        user = UserFactory()
        user.timezone = "America/New_York"
        invoice = IntervalInvoiceFactory(user=user)
        self.client.force_login(user)
        response = self.client.post(
            reverse("timary:create_hours"),
            data={
                "quantity": 1,
                "date_tracked": timezone.now().astimezone(
                    tz=zoneinfo.ZoneInfo("America/New_York")
                ),
                "invoice": invoice.id,
            },
        )
        self.assertEqual(response.status_code, 200)
        user_localtime = template_time(get_users_localtime(user), "g:i a")
        self.assertIn(
            f"{invoice.title} - {user_localtime}", response.content.decode("utf-8")
        )

    def test_get_hours_la_timezone(self):
        user = UserFactory()
        user.timezone = "America/Los_Angeles"
        user.save()
        invoice = IntervalInvoiceFactory(user=user)
        users_localtime = get_users_localtime(user)
        self.client.force_login(user)
        response = self.client.post(
            reverse("timary:create_hours"),
            data={
                "quantity": 1,
                "date_tracked": users_localtime,
                "invoice": invoice.id,
            },
        )
        self.assertEqual(response.status_code, 200)
        user_localtime = template_time(users_localtime, "g:i a")
        self.assertIn(
            f"{invoice.title} - {user_localtime}", response.content.decode("utf-8")
        )
