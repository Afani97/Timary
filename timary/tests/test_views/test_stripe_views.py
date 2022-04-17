import datetime
import json
import uuid
from unittest.mock import patch

from django.urls import reverse

from timary.models import SentInvoice
from timary.tests.factories import (
    DailyHoursFactory,
    InvoiceFactory,
    SentInvoiceFactory,
    UserFactory,
)
from timary.tests.test_views.basetest import BaseTest


class TestStripeViews(BaseTest):
    def setUp(self) -> None:
        super().setUp()

        self.user = UserFactory()
        self.client.force_login(self.user)
        self.invoice = InvoiceFactory(user=self.user)

    @classmethod
    def extract_html(cls, html):
        start = html.find("<main") + len("<main>")
        end = html.find("</main>")
        message = html[start:end]
        return message

    def test_pay_invoice_already_paid(self):
        self.client.logout()

        sent_invoice = SentInvoiceFactory(paid_status=SentInvoice.PaidStatus.PAID)
        response = self.client.get(
            reverse("timary:pay_invoice", kwargs={"sent_invoice_id": sent_invoice.id}),
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("timary:login"))

    def test_pay_invoice_raise_error_unknown_sent_invoice(self):
        self.client.logout()
        response = self.client.get(
            reverse("timary:pay_invoice", kwargs={"sent_invoice_id": uuid.uuid4()}),
        )
        self.assertEqual(response.status_code, 302)

    def test_pay_invoice_sent_invoice_valid_details(self):
        self.client.logout()
        sent_invoice = SentInvoiceFactory()
        response = self.client.post(
            reverse("timary:pay_invoice", kwargs={"sent_invoice_id": sent_invoice.id}),
            data={
                "email": sent_invoice.invoice.email_recipient,
                "first_name": sent_invoice.invoice.email_recipient_name,
            },
        )
        self.assertEqual(response.status_code, 200)
        json_content = json.loads(response.content)
        self.assertEqual(json_content, {"valid": True, "errors": {}})

    def test_pay_invoice_sent_invoice_invalid_details(self):
        self.client.logout()
        sent_invoice = SentInvoiceFactory()
        response = self.client.post(
            reverse("timary:pay_invoice", kwargs={"sent_invoice_id": sent_invoice.id}),
            data={
                "email": "user@test.com",
                "first_name": "User",
            },
        )
        self.assertEqual(response.status_code, 200)
        json_content = json.loads(response.content)
        expected_json = {
            "valid": False,
            "errors": '{"email": [{"message": "Wrong email recipient, unable to process payment", "code": ""}], '
            '"first_name": [{"message": "Wrong name recipient, unable to process payment", "code": ""}]}',
        }

        self.assertEqual(json_content, expected_json)

    @patch(
        "timary.services.stripe_service.StripeService.create_payment_intent_for_payout"
    )
    def test_pay_invoice_get_invoice_summary_and_stripe_form(self, stripe_intent_mock):
        self.client.logout()
        stripe_intent_mock.return_value = {
            "client_secret": "tok_abc123",
            "id": "abc123",
        }

        sent_invoice = SentInvoiceFactory()
        today = datetime.date.today()
        for i in range(10):
            DailyHoursFactory(
                invoice=sent_invoice.invoice,
                date_tracked=today - datetime.timedelta(days=i),
            )
        sent_invoice.refresh_from_db()
        response = self.client.get(
            reverse("timary:pay_invoice", kwargs={"sent_invoice_id": sent_invoice.id}),
        )
        self.assertEqual(response.status_code, 200)

        html_body = self.extract_html(response.content.decode("utf-8"))

        with self.subTest("Testing summary"):
            msg = f"""
            <div class="mb-4">
                <h1 class="text-2xl mb-6">Hello! Thanks for using Timary</h1>
                <p class="mb-4">This is an invoice for {sent_invoice.invoice.user.first_name}'s services.</p>
                <p>Total Amount Due: ${sent_invoice.total_price + 10}</p>
            </div>
            """
            self.assertInHTML(msg, html_body)

        with self.subTest("Testing total price in table"):
            msg = f"""
            <td width="20%" class="purchase_footer" valign="middle">
                <p class="f-fallback purchase_total">${sent_invoice.total_price + 10}</p>
            </td>
            """
            self.assertInHTML(msg, html_body)

        with self.subTest("Testing payment info form renders"):
            msg = """
            <div class="form-control my-4 col-span-2">
                <label class="label"><span class="label-text">Confirm your email</span></label>
                <input type="text" name="email" placeholder="john@appleseed.com" classes="col-span-2"
                class="input input-bordered text-lg bg-neutral
                focus:border-primary focus:ring-0 focus:ring-primary w-full"
                required id="id_email">
            </div>

            <div class="form-control my-4 col-span-2">
                <label class="label"><span class="label-text">Confirm your first name</span></label>
                <input type="text" name="first_name" placeholder="John" classes="col-span-2"
                class="input input-bordered text-lg bg-neutral
                focus:border-primary focus:ring-0 focus:ring-primary w-full"
                required id="id_first_name">
            </div>
            """
            self.assertInHTML(msg, html_body)

        with self.subTest("Testing hours table renders all hours for invoice"):
            hours_tracked = sent_invoice.get_hours_tracked()
            msg = ""
            for i, hour in enumerate(hours_tracked, start=1):
                msg += f"""
                <tr>
                    <td>{i}</td>
                    <td width="80%" class="purchase_item"><span class="f-fallback">{ hour.hours } hours on
                    { hour.date_tracked.strftime("%b %-d") }</span></td>
                    <td class="align-right" width="20%" class="purchase_item">
                    <span class="f-fallback">${ int(hour.cost)}</span>
                    </td>
                </tr>
                """
            self.assertInHTML(msg, html_body)

    def test_invoice_payment_success_invalid_invoice_id(self):
        self.client.logout()
        response = self.client.get(
            reverse(
                "timary:invoice_payment_success",
                kwargs={"sent_invoice_id": uuid.uuid4()},
            )
        )
        self.assertEqual(response.status_code, 302)

    def test_invoice_payment_success_invoice_already_paid(self):
        self.client.logout()
        sent_invoice = SentInvoiceFactory(paid_status=SentInvoice.PaidStatus.PAID)
        response = self.client.get(
            reverse(
                "timary:invoice_payment_success",
                kwargs={"sent_invoice_id": sent_invoice.id},
            )
        )
        self.assertRedirects(response, reverse("timary:login"))

    def test_invoice_payment_success_page(self):
        self.client.logout()
        sent_invoice = SentInvoiceFactory(invoice__user__phone_number=None)
        response = self.client.get(
            reverse(
                "timary:invoice_payment_success",
                kwargs={"sent_invoice_id": sent_invoice.id},
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "invoices/success_pay_invoice.html")

    @patch("timary.services.stripe_service.StripeService.create_subscription")
    @patch("timary.services.stripe_service.StripeService.get_connect_account")
    def test_onboard_success_with_payouts_enabled(
        self, stripe_connect_mock, stripe_subscription_mock
    ):
        stripe_subscription_mock.return_value = True
        stripe_connect_mock.return_value = {"payouts_enabled": True}

        self.client.force_login(self.user)

        response = self.client.get(reverse("timary:onboard_success"))
        self.user.refresh_from_db()

        self.assertRedirects(response, reverse("timary:manage_invoices"))
        self.assertTrue(self.user.stripe_payouts_enabled)

    @patch("timary.services.stripe_service.StripeService.create_subscription")
    @patch("timary.services.stripe_service.StripeService.get_connect_account")
    def test_onboard_success_with_payouts_not_enabled(
        self, stripe_connect_mock, stripe_subscription_mock
    ):
        stripe_subscription_mock.return_value = True
        stripe_connect_mock.return_value = {"payouts_enabled": False}

        self.client.force_login(self.user)

        response = self.client.get(reverse("timary:onboard_success"))
        self.user.refresh_from_db()

        self.assertRedirects(response, reverse("timary:manage_invoices"))
        self.assertFalse(self.user.stripe_payouts_enabled)

    @patch("timary.services.stripe_service.StripeService.get_connect_account")
    def test_completed_connect_account_payouts_enabled(self, stripe_connect_mock):
        stripe_connect_mock.return_value = {"payouts_enabled": True}

        self.client.force_login(self.user)

        response = self.client.get(reverse("timary:complete_connect"))
        self.user.refresh_from_db()

        self.assertRedirects(response, reverse("timary:user_profile"))
        self.assertTrue(self.user.stripe_payouts_enabled)

    @patch("timary.services.stripe_service.StripeService.get_connect_account")
    def test_completed_connect_account_payouts_not_enabled(self, stripe_connect_mock):
        stripe_connect_mock.return_value = {"payouts_enabled": False}

        self.client.force_login(self.user)

        response = self.client.get(reverse("timary:complete_connect"))
        self.user.refresh_from_db()

        self.assertRedirects(response, reverse("timary:user_profile"))
        self.assertFalse(self.user.stripe_payouts_enabled)
