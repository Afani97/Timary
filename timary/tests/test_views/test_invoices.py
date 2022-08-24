import datetime
import uuid
from unittest.mock import patch

from dateutil.relativedelta import relativedelta
from django.core import mail
from django.template.defaultfilters import date
from django.template.defaultfilters import date as template_date
from django.template.defaultfilters import floatformat
from django.urls import reverse
from django.utils.http import urlencode

from timary.models import Invoice, SentInvoice
from timary.templatetags.filters import nextmonday
from timary.tests.factories import (
    DailyHoursFactory,
    InvoiceFactory,
    SentInvoiceFactory,
    UserFactory,
)
from timary.tests.test_views.basetest import BaseTest


class TestInvoices(BaseTest):
    def setUp(self) -> None:
        super().setUp()

        self.user = UserFactory()
        self.biz_user = UserFactory(membership_tier=49)
        self.client.force_login(self.user)
        self.invoice = InvoiceFactory(user=self.user)
        self.invoice_no_user = InvoiceFactory()
        self.biz_invoice = InvoiceFactory(user=self.biz_user)

    @classmethod
    def extract_html(cls):
        s = mail.outbox[0].message().as_string()
        start = s.find("<body>") + len("<body>")
        end = s.find("</body>")
        message = s[start:end]
        return message

    @patch(
        "timary.services.stripe_service.StripeService.create_customer_for_invoice",
        return_value=None,
    )
    def test_create_invoice(self, customer_mock):
        Invoice.objects.all().delete()
        response = self.client.post(
            reverse("timary:create_invoice"),
            {
                "title": "Some title",
                "invoice_rate": 50,
                "invoice_type": 1,
                "invoice_interval": "D",
                "email_recipient_name": "John Smith",
                "email_recipient": "john@test.com",
            },
        )

        invoice = Invoice.objects.first()
        inv_name = invoice.email_recipient_name
        inv_email = invoice.email_recipient
        self.assertInHTML(
            f"""
            <h2 class="card-title">{invoice.title} - Rate: ${invoice.invoice_rate}</h2>
            """,
            response.content.decode("utf-8"),
        )
        self.assertInHTML(
            f"""
            <p class="text-xl">emailed daily to {inv_name} ({inv_email})</p>
            <p class="text-xl">next date sent is {invoice.next_date.strftime("%b. %-d, %Y")}</p>
            """,
            response.content.decode("utf-8"),
        )
        self.assertEqual(response.templates[0].name, "partials/_invoice.html")
        self.assertEqual(response.status_code, 200)

    @patch(
        "timary.services.stripe_service.StripeService.create_customer_for_invoice",
        return_value=None,
    )
    def test_create_invoice_milestone(self, customer_mock):
        Invoice.objects.all().delete()
        response = self.client.post(
            reverse("timary:create_invoice"),
            {
                "title": "Some title",
                "invoice_rate": 50,
                "invoice_type": 2,
                "milestone_total_steps": 3,
                "email_recipient_name": "John Smith",
                "email_recipient": "john@test.com",
            },
        )
        invoice = Invoice.objects.first()
        inv_name = invoice.email_recipient_name
        inv_email = invoice.email_recipient
        self.assertInHTML(
            f"""
                <p class="text-xl my-2">emailed to {inv_name} ({inv_email})</p>
                <div class="grid grid-cols-1 sm:grid-cols-4 items-baseline">
                <ul class="steps grow col-span-3">
                <li class="step step-primary">current</li><li class="step"></li><li class="step"></li>
                </ul>
                <a hx-get="{reverse("timary:generate_invoice", kwargs={"invoice_id": invoice.id})}"
                    hx-confirm="Are you sure you want to complete this milestone?"
                    hx-target="closest #some-title" hx-swap="innerHTML" class="btn btn-secondary mt-5"
                    _="on htmx:beforeRequest add .loading to me end on htmx:afterRequest remove .loading from me">
                    Complete current milestone
                </a>
                </div>
                """,
            response.content.decode("utf-8"),
        )
        self.assertEqual(response.templates[0].name, "partials/_invoice.html")
        self.assertEqual(response.status_code, 200)

    @patch(
        "timary.services.stripe_service.StripeService.create_customer_for_invoice",
        return_value=None,
    )
    def test_create_weekly_invoice(self, customer_mock):
        Invoice.objects.all().delete()
        response = self.client.post(
            reverse("timary:create_invoice"),
            {
                "title": "Some title",
                "invoice_type": 3,
                "weekly_rate": 1200,
                "email_recipient_name": "John Smith",
                "email_recipient": "john@test.com",
            },
        )
        invoice = Invoice.objects.first()
        inv_name = invoice.email_recipient_name
        inv_email = invoice.email_recipient
        self.assertInHTML(
            f"""
            <p class="text-xl my-2">emailed to {inv_name} ({inv_email})</p>
            <p class="text-xl">next invoice sent out: {template_date(nextmonday(""), "M. j, Y")}</p>
            """,
            response.content.decode("utf-8"),
        )
        self.assertEqual(response.templates[0].name, "partials/_invoice.html")
        self.assertEqual(response.status_code, 200)

    def test_manage_invoices(self):
        response = self.client.get(reverse("timary:manage_invoices"))
        self.assertContains(
            response,
            f'<h2 class="card-title">{self.invoice.title} - Rate: ${self.invoice.invoice_rate}</h2>',
        )
        self.assertTemplateUsed(response, "invoices/manage_invoices.html")
        self.assertEqual(response.status_code, 200)

    def test_manage_zero_invoices(self):
        Invoice.objects.filter(user=self.user).all().delete()
        response = self.client.get(reverse("timary:manage_invoices"))
        self.assertInHTML(
            """
            <div class="text-center lg:text-left md:mr-20">
                <h1 class="mb-5 text-5xl font-bold" id="intro-text">
                    Hello there
                </h1>
                <p class="mb-5">
                    We all gotta start somewhere right? Begin your journey by adding your first invoicing details.
                </p>
            </div>
            """,
            response.content.decode("utf-8"),
        )
        self.assertTemplateUsed(response, "invoices/manage_invoices.html")
        self.assertEqual(response.status_code, 200)

    def test_zero_invoices_redirects_main_page(self):
        Invoice.objects.filter(user=self.user).all().delete()
        response = self.client.get(reverse("timary:index"))
        self.assertRedirects(response, reverse("timary:manage_invoices"))
        self.assertEqual(response.status_code, 302)

    @patch(
        "timary.services.stripe_service.StripeService.create_customer_for_invoice",
        return_value=None,
    )
    def test_create_invoice_error(self, customer_mock):
        invoice = self.user.get_invoices.first()
        response = self.client.post(
            reverse("timary:create_invoice"),
            {
                "title": invoice.title,
                "invoice_rate": 50,
                "invoice_type": 1,
                "invoice_interval": "D",
                "email_recipient_name": "John Smith",
                "email_recipient": "john@test.com",
            },
        )
        self.assertInHTML(
            "Duplicate invoice title not allowed.", response.content.decode("utf-8")
        )

    def test_get_invoice(self):
        rendered_template = self.setup_template(
            "partials/_invoice.html", {"invoice": self.invoice}
        )
        response = self.client.get(
            reverse("timary:get_single_invoice", kwargs={"invoice_id": self.invoice.id})
        )
        self.assertHTMLEqual(rendered_template, response.content.decode("utf-8"))

    def test_get_invoice_with_hours_logged(self):
        self.client.force_login(self.biz_user)
        hour = DailyHoursFactory(invoice=self.biz_invoice)

        rendered_template = self.setup_template(
            "partials/_invoice.html", {"invoice": self.biz_invoice}
        )
        response = self.client.get(
            reverse(
                "timary:get_single_invoice", kwargs={"invoice_id": self.biz_invoice.id}
            )
        )
        self.assertHTMLEqual(rendered_template, response.content.decode("utf-8"))
        self.assertInHTML(
            f"""<ul class="list-none">
                <li class="text-xl">{floatformat(hour.hours, 2)} hrs on {date(hour.date_tracked, "M jS")}</li>
           </ul>""",
            response.content.decode("utf-8"),
        )
        self.client.force_login(self.user)

    def test_starter_or_professional_cannot_view_invoice_stats(self):
        self.client.force_login(self.user)
        hour = DailyHoursFactory(invoice=self.invoice)
        response = self.client.get(
            reverse("timary:get_single_invoice", kwargs={"invoice_id": hour.invoice.id})
        )
        with self.assertRaises(AssertionError):
            self.assertInHTML(
                "View hours logged this period",
                response.content.decode("utf-8"),
            )

    def test_biz_can_view_invoice_stats(self):
        self.client.force_login(self.biz_user)
        DailyHoursFactory(invoice=self.biz_invoice)
        response = self.client.get(
            reverse(
                "timary:get_single_invoice", kwargs={"invoice_id": self.biz_invoice.id}
            )
        )
        self.assertInHTML(
            "View more",
            response.content.decode("utf-8"),
        )
        self.client.force_login(self.user)

    def test_get_invoice_error(self):
        response = self.client.get(
            reverse(
                "timary:get_single_invoice",
                kwargs={"invoice_id": self.invoice_no_user.id},
            )
        )
        self.assertEqual(response.status_code, 302)

    def test_edit_invoice(self):
        response = self.client.get(
            reverse("timary:edit_invoice", kwargs={"invoice_id": self.invoice.id}),
        )
        self.assertEqual(response.status_code, 200)

    def test_edit_invoice_error(self):
        response = self.client.get(
            reverse(
                "timary:edit_invoice", kwargs={"invoice_id": self.invoice_no_user.id}
            ),
            data={},
        )
        self.assertEqual(response.status_code, 302)

    def test_update_invoice(self):
        url_params = {
            "title": "Some title",
            "invoice_rate": 100,
            "invoice_interval": "D",
            "email_recipient_name": "John Smith",
            "email_recipient": "john@test.com",
        }
        response = self.client.put(
            reverse("timary:update_invoice", kwargs={"invoice_id": self.invoice.id}),
            data=urlencode(url_params),  # HTML PUT FORM
        )
        self.invoice.refresh_from_db()
        inv_name = self.invoice.email_recipient_name
        inv_email = self.invoice.email_recipient
        self.assertInHTML(
            f"""
            <h2 class="card-title">{self.invoice.title} - Rate: ${self.invoice.invoice_rate}</h2>
            """,
            response.content.decode("utf-8"),
        )
        self.assertInHTML(
            f"""
            <p class="text-xl">emailed daily to {inv_name} ({inv_email})</p>
            <p class="text-xl">next date sent is {self.invoice.next_date.strftime("%b. %-d, %Y")}</p>
            """,
            response.content.decode("utf-8"),
        )
        self.assertEqual(response.templates[0].name, "partials/_invoice.html")
        self.assertEqual(response.status_code, 200)

    def test_update_invoice_milestone(self):
        invoice = InvoiceFactory(invoice_type=2, user=self.user, milestone_step=3)
        url_params = {
            "title": "Some title",
            "invoice_rate": 100,
            "milestone_total_steps": 5,
            "email_recipient_name": "John Smith",
            "email_recipient": "john@test.com",
        }
        response = self.client.put(
            reverse("timary:update_invoice", kwargs={"invoice_id": invoice.id}),
            data=urlencode(url_params),  # HTML PUT FORM
        )
        invoice.refresh_from_db()
        inv_name = invoice.email_recipient_name
        inv_email = invoice.email_recipient
        self.assertInHTML(
            f"""
            <p class="text-xl my-2">emailed to {inv_name} ({inv_email})</p>
            <div class="grid grid-cols-1 sm:grid-cols-4 items-baseline">
            <ul class="steps grow col-span-3">
            <li class="step step-primary"></li>
            <li class="step step-primary"></li>
            <li class="step step-primary">current</li>
            <li class="step"></li>
            <li class="step"></li>
            </ul>
            <a hx-get="{reverse("timary:generate_invoice", kwargs={"invoice_id": invoice.id})}"
                hx-confirm="Are you sure you want to complete this milestone?"
                hx-target="closest #some-title" hx-swap="innerHTML" class="btn btn-secondary mt-5"
                _="on htmx:beforeRequest add .loading to me end on htmx:afterRequest remove .loading from me">
                Complete current milestone
            </a>
            </div>
            """,
            response.content.decode("utf-8"),
        )
        self.assertEqual(response.templates[0].name, "partials/_invoice.html")
        self.assertEqual(response.status_code, 200)

    def test_update_weekly_invoice(self):
        invoice = InvoiceFactory(invoice_type=3, user=self.user, invoice_rate=50)
        url_params = {
            "title": "Some title",
            "weekly_rate": 100,
            "email_recipient_name": "John Smith",
            "email_recipient": "john@test.com",
        }
        response = self.client.put(
            reverse("timary:update_invoice", kwargs={"invoice_id": invoice.id}),
            data=urlencode(url_params),  # HTML PUT FORM
        )
        invoice.refresh_from_db()
        self.assertEqual(response.templates[0].name, "partials/_invoice.html")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(invoice.invoice_rate, 100)

    def test_update_invoice_dont_update_next_date_if_none(self):
        url_params = {
            "title": "Some title",
            "invoice_rate": 100,
            "invoice_interval": "D",
            "email_recipient_name": "John Smith",
            "email_recipient": "john@test.com",
        }
        self.invoice.next_date = None
        self.invoice.save()
        response = self.client.put(
            reverse("timary:update_invoice", kwargs={"invoice_id": self.invoice.id}),
            data=urlencode(url_params),  # HTML PUT FORM
        )
        self.invoice.refresh_from_db()
        self.assertIsNone(self.invoice.next_date)
        self.assertInHTML(
            """<p class="text-xl">invoice is paused</p>""",
            response.content.decode("utf-8"),
        )
        self.assertEqual(response.templates[0].name, "partials/_invoice.html")
        self.assertEqual(response.status_code, 200)

    def test_update_invoice_error(self):
        response = self.client.put(
            reverse(
                "timary:update_invoice", kwargs={"invoice_id": self.invoice_no_user.id}
            ),
            data={},
        )
        self.assertEqual(response.status_code, 302)

    def test_pause_invoice(self):
        invoice = InvoiceFactory(invoice_interval="M", user=self.user)
        response = self.client.get(
            reverse("timary:pause_invoice", kwargs={"invoice_id": invoice.id}),
        )
        invoice.refresh_from_db()
        self.assertIsNone(invoice.next_date)
        self.assertEqual(response.templates[0].name, "partials/_invoice.html")
        self.assertEqual(response.status_code, 200)

        response = self.client.get(
            reverse("timary:pause_invoice", kwargs={"invoice_id": invoice.id}),
        )
        invoice.refresh_from_db()

        self.assertEqual(
            invoice.next_date,
            datetime.date.today() + invoice.get_next_date(),
        )
        self.assertEqual(response.templates[0].name, "partials/_invoice.html")
        self.assertEqual(response.status_code, 200)

    def test_pause_invoice_does_not_override_last_date(self):
        """
        Paused invoices shouldn't override the last date when unpaused
        since hours may be tracked prior and are not included in next sent invoice.
        """

        # Pause invoice
        invoice = InvoiceFactory(invoice_interval="M", user=self.user)
        hours1 = DailyHoursFactory(invoice=invoice)
        response = self.client.get(
            reverse("timary:pause_invoice", kwargs={"invoice_id": invoice.id}),
        )
        invoice.refresh_from_db()
        self.assertIsNone(invoice.next_date)
        self.assertEqual(response.templates[0].name, "partials/_invoice.html")
        self.assertEqual(response.status_code, 200)

        # Unpause invoice
        response = self.client.get(
            reverse("timary:pause_invoice", kwargs={"invoice_id": invoice.id}),
        )
        invoice.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, "partials/_invoice.html")
        self.assertEqual(
            invoice.next_date,
            datetime.date.today() + invoice.get_next_date(),
        )
        self.assertIn(hours1, invoice.get_hours_tracked())

    def test_pause_invoice_error(self):
        response = self.client.get(
            reverse(
                "timary:pause_invoice", kwargs={"invoice_id": self.invoice_no_user.id}
            ),
            data={},
        )
        self.assertEqual(response.status_code, 302)

    def test_archive_invoice(self):
        Invoice.objects.all().delete()
        invoice = InvoiceFactory(user=self.user)
        response = self.client.get(
            reverse("timary:archive_invoice", kwargs={"invoice_id": invoice.id}),
        )
        self.user.refresh_from_db()
        invoice.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(invoice.is_archived)
        self.assertEqual(self.user.get_invoices.count(), 0)

    def test_archive_invoice_error(self):
        response = self.client.get(
            reverse(
                "timary:archive_invoice", kwargs={"invoice_id": self.invoice_no_user.id}
            ),
            data={},
        )
        self.assertEqual(response.status_code, 302)

    def test_resend_invoice_email(self):
        invoice = InvoiceFactory(user=self.user)
        sent_invoice = SentInvoiceFactory(invoice=invoice)

        response = self.client.get(
            reverse(
                "timary:resend_invoice_email",
                kwargs={"sent_invoice_id": sent_invoice.id},
            ),
        )
        self.assertEqual(len(mail.outbox), 1)
        expected_context = {"sent_invoice": sent_invoice, "invoice_resent": True}
        expected_response = self.setup_template(
            "partials/_sent_invoice.html", expected_context
        )
        self.assertEqual(expected_response, response.content.decode("utf-8"))

    def test_resend_invoice_email_already_paid(self):
        invoice = InvoiceFactory(user=self.user)
        sent_invoice = SentInvoiceFactory(
            invoice=invoice, paid_status=SentInvoice.PaidStatus.PAID
        )

        response = self.client.get(
            reverse(
                "timary:resend_invoice_email",
                kwargs={"sent_invoice_id": sent_invoice.id},
            ),
        )
        self.assertRedirects(response, reverse("timary:user_profile"))

    def test_resend_invoice_email_error(self):
        response = self.client.get(
            reverse(
                "timary:resend_invoice_email",
                kwargs={"sent_invoice_id": uuid.uuid4()},
            ),
        )
        self.assertEqual(response.status_code, 302)

    def test_create_invoice_btn_message_as_starter(self):
        self.client.logout()
        user = UserFactory(membership_tier=5)
        self.client.force_login(user)

        InvoiceFactory(user=user)

        response = self.client.get(
            reverse(
                "timary:create_invoice_btn",
            ),
        )

        self.assertIn(
            "Upgrade your membership tier to Professional or Business or Invoice Fee to create new invoices.",
            response.content.decode("utf-8"),
        )

    def test_create_invoice_btn_message_as_professional(self):
        self.client.logout()
        user = UserFactory()
        self.client.force_login(user)

        InvoiceFactory(user=user)
        InvoiceFactory(user=user)

        response = self.client.get(
            reverse(
                "timary:create_invoice_btn",
            ),
        )

        self.assertIn(
            "Upgrade your membership tier to Business or Invoice Fee to create new invoices.",
            response.content.decode("utf-8"),
        )

    def test_total_invoice_stats(self):
        self.client.logout()
        self.client.force_login(self.user)

        hours1 = DailyHoursFactory(invoice__user=self.user)
        hours2 = DailyHoursFactory(invoice__user=self.user)
        s1 = SentInvoiceFactory(invoice=hours1.invoice, user=self.user)
        s2 = SentInvoiceFactory(
            invoice=hours2.invoice,
            user=self.user,
            paid_status=SentInvoice.PaidStatus.PAID,
        )

        response = self.client.get(
            reverse(
                "timary:manage_invoices",
            ),
        )

        self.assertInHTML(
            f"""
            <div class="stats shadow">
              <div class="stat place-items-center">
                <div class="stat-value">${int(s1.total_price) }</div>
                <div class="stat-desc">owed</div>
              </div>

              <div class="stat place-items-center">
                <div class="stat-value">${ int(s2.total_price) }</div>
                <div class="stat-desc">total earned</div>
              </div>
            </div>""",
            response.content.decode("utf-8"),
        )

    def test_total_invoice_last_six_months(self):
        user = UserFactory(membership_tier=49)
        self.client.force_login(user)

        invoice = InvoiceFactory(user=user)
        today = datetime.date.today()
        hours = [DailyHoursFactory(invoice=invoice)]
        for i in range(1, 6):
            hours.append(
                DailyHoursFactory(
                    invoice=invoice, date_tracked=(today - relativedelta(months=i))
                )
            )
        hours.sort(key=lambda h: h.date_tracked)
        max_hr = int(max(hour.hours for hour in hours))

        hours = "".join(
            list(
                map(
                    lambda h: f"""
                    <tr><th scope="row">{ h.date_tracked.strftime("%b") }</th>
                    <td style="--size:{round((h.hours / (max_hr + 100)), 2)};">
                    <span class="tooltip"> { round(h.hours, 2) }h, ${round(h.hours) * invoice.invoice_rate}</span>
                    </td></tr>""",
                    hours,
                )
            )
        )
        response = self.client.get(
            reverse("timary:get_single_invoice", kwargs={"invoice_id": invoice.id}),
        )

        self.assertInHTML(f"<tbody>{hours}</tbody>", response.content.decode("utf-8"))

    def test_generate_invoice(self):
        todays_date = datetime.date.today()
        current_month = datetime.date.strftime(todays_date, "%m/%Y")
        hours = DailyHoursFactory(invoice=self.invoice)
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("timary:generate_invoice", kwargs={"invoice_id": self.invoice.id}),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEquals(len(mail.outbox), 1)
        self.assertEquals(
            mail.outbox[0].subject,
            f"{hours.invoice.title}'s Invoice from {hours.invoice.user.first_name} for {current_month}",
        )
        self.assertTemplateUsed(response, "partials/_invoice.html")

    def test_generate_invoice_milestone(self):
        invoice = InvoiceFactory(
            invoice_type=Invoice.InvoiceType.MILESTONE,
            milestone_step=3,
            milestone_total_steps=6,
            user=self.user,
        )
        DailyHoursFactory(invoice=invoice)
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("timary:generate_invoice", kwargs={"invoice_id": invoice.id}),
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.milestone_step, 4)
        self.assertEqual(response.status_code, 200)
        self.assertEquals(len(mail.outbox), 1)

    def test_get_hour_forms_for_invoice(self):
        """Only hours1 and hours2 show since its date_tracked
        is within invoice's last date and current date"""
        hours1 = DailyHoursFactory(invoice=self.invoice)
        hours2 = DailyHoursFactory(invoice=self.invoice)
        hours3 = DailyHoursFactory(
            invoice=self.invoice,
            date_tracked=datetime.date.today() - relativedelta(months=2),
        )
        response = self.client.get(
            reverse("timary:edit_invoice_hours", kwargs={"invoice_id": self.invoice.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, "partials/_edit_hours.html")
        self.assertInHTML(
            f"""
            <input type="text" name="hours" value="{str(round(hours1.hours, 2))}" value="1.0"
            class="input input-bordered text-lg hours-input w-full"
            _="on input call filterHoursInput(me) end on blur call convertHoursInput(me) end" required id="id_hours">
            """,
            response.content.decode("utf-8"),
        )
        self.assertInHTML(
            f"""
            <input type="text" name="hours" value="{str(round(hours2.hours, 2))}" value="1.0"
            class="input input-bordered text-lg hours-input w-full"
            _="on input call filterHoursInput(me) end on blur call convertHoursInput(me) end" required id="id_hours">
            """,
            response.content.decode("utf-8"),
        )
        self.assertNotIn(
            f"""
            <input type="text" name="hours" value="{str(round(hours3.hours, 2))}" value="1.0"
            class="input input-bordered text-lg hours-input w-full"
            _="on input call filterHoursInput(me) end on blur call convertHoursInput(me) end" required id="id_hours">
            """,
            response.content.decode("utf-8"),
        )
