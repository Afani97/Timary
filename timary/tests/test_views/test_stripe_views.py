import json
import uuid
import zoneinfo
from decimal import Decimal
from unittest.mock import patch

from django.core import mail
from django.template.defaultfilters import date as template_date
from django.template.defaultfilters import floatformat
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from timary.models import SentInvoice, User
from timary.tests.factories import (
    HoursLineItemFactory,
    IntervalInvoiceFactory,
    LineItemFactory,
    SentInvoiceFactory,
    SingleInvoiceFactory,
    UserFactory,
)
from timary.tests.test_views.basetest import BaseTest


class TestStripeViews(BaseTest):
    def setUp(self) -> None:
        super().setUp()

        self.user = UserFactory()
        self.client.force_login(self.user)
        self.invoice = IntervalInvoiceFactory(user=self.user)

    @classmethod
    def extract_html(cls, html):
        start = html.find("<main") + len("<main>")
        end = html.find("</main>")
        message = html[start:end]
        return message

    @classmethod
    def extract_html_body(cls):
        s = mail.outbox[0].message().as_string()
        start = s.find("<body>") + len("<body>")
        end = s.find("</body>")
        message = s[start:end]
        return message

    def test_pay_invoice_already_paid(self):
        self.client.logout()

        sent_invoice = SentInvoiceFactory(paid_status=SentInvoice.PaidStatus.PAID)
        response = self.client.get(
            reverse("timary:pay_invoice", kwargs={"sent_invoice_id": sent_invoice.id}),
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("timary:landing_page"))

    def test_pay_invoice_redirect_cancelled_invoice(self):
        self.client.logout()

        sent_invoice = SentInvoiceFactory(paid_status=SentInvoice.PaidStatus.CANCELLED)
        response = self.client.get(
            reverse("timary:pay_invoice", kwargs={"sent_invoice_id": sent_invoice.id}),
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("timary:landing_page"))

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
                "email": sent_invoice.invoice.client.email,
                "first_name": sent_invoice.invoice.client.name,
            },
        )
        self.assertEqual(response.status_code, 200)
        json_content = json.loads(response.content)
        self.assertEqual(json_content, {"valid": True, "errors": {}})

    def test_pay_invoice_sent_invoice_invalid_details(self):
        self.maxDiff = None
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
        json_content = json.loads(response.content.decode())
        expected_json = {
            "valid": False,
            "errors": {
                "email": ["Unable to process payment, please enter correct details."],
                "first_name": [
                    "Unable to process payment, please enter correct details."
                ],
            },
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
        today = timezone.now()
        for i in range(10):
            HoursLineItemFactory(
                invoice=sent_invoice.invoice,
                date_tracked=today - timezone.timedelta(days=i),
                sent_invoice_id=sent_invoice.id,
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
                <p class="mb-4">This is an invoice for
                {sent_invoice.user.invoice_branding_properties()["user_name"]}'s services.</p>
                <p>Total Amount Due: ${sent_invoice.total_price + 5}</p>
            </div>
            """
            self.assertInHTML(msg, html_body)

        with self.subTest("Testing total price in table"):
            self.assertIn(f"{Decimal(sent_invoice.total_price + 5)}", html_body)

        with self.subTest("Testing payment info form renders"):
            msg = """
            <div class="form-control my-4 col-span-2">
                <label class="label"><span class="label-text">Confirm your email</span></label>
                <input type="text" name="email" placeholder="john@appleseed.com" classes="col-span-2"
                class="input input-bordered border-2 text-lg bg-neutral
                focus:border-primary focus:ring-0 focus:ring-primary w-full"
                required id="id_email">
            </div>

            <div class="form-control my-4 col-span-2">
                <label class="label"><span class="label-text">Confirm your first name</span></label>
                <input type="text" name="first_name" placeholder="John" classes="col-span-2"
                class="input input-bordered border-2 text-lg bg-neutral
                focus:border-primary focus:ring-0 focus:ring-primary w-full"
                required id="id_first_name">
            </div>
            """
            self.assertInHTML(msg, html_body)

        with self.subTest("Testing hours table renders all hours for invoice"):
            self.assertInHTML(sent_invoice.get_rendered_line_items(), html_body)

    @patch(
        "timary.services.stripe_service.StripeService.create_payment_intent_for_payout"
    )
    def test_pay_single_invoice_get_invoice_summary_and_stripe_form(
        self, stripe_intent_mock
    ):
        self.client.logout()
        stripe_intent_mock.return_value = {
            "client_secret": "tok_abc123",
            "id": "abc123",
        }

        single_invoice = SingleInvoiceFactory()
        sent_invoice = SentInvoiceFactory(invoice=single_invoice)
        today = timezone.now()
        LineItemFactory(
            quantity=1,
            unit_price=1,
            invoice=sent_invoice.invoice,
            date_tracked=today,
            sent_invoice_id=sent_invoice.id,
        )
        LineItemFactory(
            quantity=2,
            unit_price=2.5,
            invoice=sent_invoice.invoice,
            date_tracked=today,
            sent_invoice_id=sent_invoice.id,
        )
        single_invoice.update()
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
                <p class="mb-4">This is an invoice for
                {sent_invoice.user.invoice_branding_properties()["user_name"]}'s services.</p>
                <p>Total Amount Due: $11</p>
            </div>
            """
            self.assertInHTML(msg, html_body)

        with self.subTest("Testing hours table renders all hours for invoice"):
            self.assertInHTML(sent_invoice.get_rendered_line_items(), html_body)

    @patch(
        "timary.services.stripe_service.StripeService.create_payment_intent_for_payout"
    )
    def test_pay_single_invoice_update_total_price_if_late(self, stripe_intent_mock):
        stripe_intent_mock.return_value = {
            "client_secret": "tok_abc123",
            "id": "abc123",
        }

        today = timezone.now()
        late_penalty_amount = 100
        single_invoice = SingleInvoiceFactory(
            late_penalty=True,
            late_penalty_amount=late_penalty_amount,
            due_date=today,
            status=1,
            user=self.user,
            balance_due=2,
        )

        li = LineItemFactory(
            quantity=2,
            unit_price=1,
            invoice=single_invoice,
            date_tracked=today,
        )

        # Generate sent invoice
        self.client.get(
            reverse(
                "timary:send_single_invoice_email",
                kwargs={"single_invoice_id": single_invoice.id},
            ),
        )
        self.client.logout()
        sent_invoice = single_invoice.get_sent_invoice()

        with patch("timary.models.SingleInvoice.is_payment_late", return_value=True):
            response = self.client.get(
                reverse(
                    "timary:pay_invoice", kwargs={"sent_invoice_id": sent_invoice.id}
                ),
            )
            self.assertEqual(response.status_code, 200)

            html_body = self.extract_html(response.content.decode("utf-8"))
            total_due = late_penalty_amount + li.total_amount() + 5  # stripe fee
            with self.subTest("Testing summary"):
                msg = f"""
                    <div class="mb-4">
                        <h1 class="text-2xl mb-6">Hello! Thanks for using Timary</h1>
                        <p class="mb-4">This is an invoice for
                        {sent_invoice.user.invoice_branding_properties()["user_name"]}'s services.</p>
                        <p>Total Amount Due: ${total_due}</p>
                    </div>
                    """
                self.assertInHTML(msg, html_body)
            with self.subTest("Testing late penalty msg appears"):
                self.assertInHTML(
                    """<div class="text-sm -mt-3 pb-3">Penalty added because this is past due.</div>""",
                    html_body,
                )

    @patch(
        "timary.services.stripe_service.StripeService.create_payment_intent_for_payout"
    )
    @patch(
        "timary.services.stripe_service.StripeService.retrieve_customer_payment_method"
    )
    def test_quick_pay_invoice_button_displays(
        self, stripe_customer_mock, stripe_intent_mock
    ):
        """Quick pay only shows if user has previously paid using ACH Debit"""
        self.client.logout()
        stripe_customer_mock.return_value = {"us_bank_account": {"last4": "1234"}}
        stripe_intent_mock.return_value = {
            "client_secret": "tok_abc123",
            "id": "abc123",
        }

        sent_invoice = SentInvoiceFactory(invoice__client__stripe_customer_id=12345)
        HoursLineItemFactory(invoice=sent_invoice.invoice)
        sent_invoice.refresh_from_db()
        response = self.client.get(
            reverse("timary:pay_invoice", kwargs={"sent_invoice_id": sent_invoice.id}),
        )
        self.assertEqual(response.status_code, 200)

        html_body = self.extract_html(response.content.decode("utf-8"))

        msg = """
            <button id="quick-pay" class="flex self-center btn btn-primary">
                Use saved bank account ending in 1234
            </button>
            """
        self.assertInHTML(msg, html_body)

    @patch(
        "timary.services.stripe_service.StripeService.create_payment_intent_for_payout"
    )
    @patch(
        "timary.services.stripe_service.StripeService.retrieve_customer_payment_method"
    )
    def test_quick_pay_invoice_button_not_available_if_no_valid_payment_method(
        self, stripe_customer_mock, stripe_intent_mock
    ):
        """Quick pay does not show if customer does not have an attached payment method"""
        self.client.logout()
        stripe_customer_mock.return_value = None
        stripe_intent_mock.return_value = {
            "client_secret": "tok_abc123",
            "id": "abc123",
        }

        sent_invoice = SentInvoiceFactory(invoice__client__stripe_customer_id=12345)
        HoursLineItemFactory(invoice=sent_invoice.invoice)
        sent_invoice.refresh_from_db()
        response = self.client.get(
            reverse("timary:pay_invoice", kwargs={"sent_invoice_id": sent_invoice.id}),
        )
        self.assertEqual(response.status_code, 200)

        html_body = self.extract_html(response.content.decode("utf-8"))
        msg = """
                <button id="quick-pay" class="flex self-center btn btn-primary">
                    Use saved bank account ending in 1234
                </button>
                """
        self.assertNotIn(msg, html_body)

    def test_invoice_payment_no_active_subscription(self):
        sent_invoice = SentInvoiceFactory(
            paid_status=SentInvoice.PaidStatus.NOT_STARTED
        )
        sent_invoice.user.stripe_subscription_status = 3
        sent_invoice.user.save()
        self.client.force_login(sent_invoice.user)
        response = self.client.get(
            reverse(
                "timary:pay_invoice",
                kwargs={"sent_invoice_id": sent_invoice.id},
            )
        )
        self.assertEqual(response.status_code, 302)

    @patch("timary.services.stripe_service.StripeService.confirm_payment")
    def test_quick_pay_confirm(self, stripe_payment_mock):
        stripe_payment_mock.return_value = {"id": "12345"}

        sent_invoice = SentInvoiceFactory(invoice__client__stripe_customer_id=12345)
        HoursLineItemFactory(invoice=sent_invoice.invoice)
        sent_invoice.refresh_from_db()

        response = self.client.get(
            reverse(
                "timary:quick_pay_invoice", kwargs={"sent_invoice_id": sent_invoice.id}
            )
        )
        self.assertEqual(response.status_code, 200)
        json_content = json.loads(response.content)

        self.assertIsNotNone(json_content["return_url"])

    @patch("timary.services.stripe_service.StripeService.confirm_payment")
    def test_quick_pay_confirm_fails(self, stripe_payment_mock):
        stripe_payment_mock.return_value = None

        sent_invoice = SentInvoiceFactory(invoice__client__stripe_customer_id=12345)
        HoursLineItemFactory(invoice=sent_invoice.invoice)
        sent_invoice.refresh_from_db()

        response = self.client.get(
            reverse(
                "timary:quick_pay_invoice", kwargs={"sent_invoice_id": sent_invoice.id}
            )
        )
        self.assertEqual(response.status_code, 200)
        json_content = json.loads(response.content)

        self.assertIsNotNone(json_content["error"])

    def test_quick_pay_confirm_redirect(self):
        sent_invoice = SentInvoiceFactory(paid_status=2)
        response = self.client.get(
            reverse(
                "timary:quick_pay_invoice", kwargs={"sent_invoice_id": sent_invoice.id}
            )
        )
        self.assertRedirects(
            response, reverse("timary:landing_page"), target_status_code=200
        )

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

    @patch("timary.services.stripe_service.StripeService.create_new_subscription")
    @patch("timary.services.stripe_service.StripeService.get_connect_account")
    def test_onboard_success_with_payouts_not_enabled(
        self, stripe_connect_mock, stripe_subscription_mock
    ):
        stripe_subscription_mock.return_value = True
        stripe_connect_mock.return_value = {"payouts_enabled": False}

        self.client.force_login(self.user)

        response = self.client.get(
            f"{reverse('timary:onboard_success')}?user_id={self.user.id}"
        )
        self.user.refresh_from_db()

        self.assertRedirects(response, reverse("timary:manage_invoices"))
        self.assertFalse(self.user.stripe_payouts_enabled)

    @patch("timary.services.stripe_service.StripeService.create_new_subscription")
    @patch("timary.services.stripe_service.StripeService.get_connect_account")
    def test_onboard_success_without_user_redirects_to_register(
        self, stripe_connect_mock, stripe_subscription_mock
    ):
        stripe_subscription_mock.return_value = True
        stripe_connect_mock.return_value = {"payouts_enabled": False}
        response = self.client.get(reverse("timary:onboard_success"))
        self.user.refresh_from_db()

        self.assertRedirects(
            response, reverse("timary:register"), target_status_code=302
        )
        self.assertFalse(self.user.stripe_payouts_enabled)

    @patch("timary.services.stripe_service.StripeService.create_new_subscription")
    @patch("timary.services.stripe_service.StripeService.get_connect_account")
    def test_onboard_success_invalid_user_id(
        self, stripe_connect_mock, stripe_subscription_mock
    ):
        stripe_subscription_mock.return_value = True
        stripe_connect_mock.return_value = {"payouts_enabled": True}

        self.client.force_login(self.user)

        response = self.client.get(
            f"{reverse('timary:onboard_success')}?user_id={uuid.uuid4()}"
        )
        self.user.refresh_from_db()

        self.assertRedirects(
            response, reverse("timary:register"), target_status_code=302
        )
        self.assertFalse(self.user.stripe_payouts_enabled)

    @patch("stripe.Webhook.construct_event")
    @patch("timary.models.SentInvoice.success_notification")
    def test_stripe_webhook_payment_success(
        self, success_notification_mock, stripe_webhook_mock
    ):
        success_notification_mock.return_value = None
        stripe_webhook_mock.return_value = {
            "type": "charge.succeeded",
            "data": {"object": {"id": "abc123"}},
        }
        sent_invoice = SentInvoiceFactory(stripe_payment_intent_id="abc123")

        response = self.client.post(
            reverse("timary:stripe_webhook"), data={}, HTTP_STRIPE_SIGNATURE="abc123"
        )
        sent_invoice.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(sent_invoice.paid_status, SentInvoice.PaidStatus.PAID)

    @patch("stripe.Webhook.construct_event")
    def test_stripe_webhook_payment_error(self, stripe_webhook_mock):
        sent_invoice = SentInvoiceFactory(stripe_payment_intent_id="abc123")
        stripe_webhook_mock.return_value = {
            "type": "payment_intent.payment_failed",
            "data": {"object": {"id": "abc123"}},
        }

        response = self.client.post(
            reverse("timary:stripe_webhook"), data={}, HTTP_STRIPE_SIGNATURE="abc123"
        )
        sent_invoice.refresh_from_db()

        html_subject = (
            f"Unable to process {sent_invoice.invoice.user.first_name}'s invoice. "
            f"An error occurred while trying to transfer the funds for this invoice. "
            f"Please give it another try."
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(sent_invoice.paid_status, SentInvoice.PaidStatus.FAILED)
        self.assertEqual(mail.outbox[0].subject, html_subject)

    @patch("stripe.Webhook.construct_event")
    def test_stripe_webhook_payment_error_email_invoice(self, stripe_webhook_mock):
        stripe_webhook_mock.return_value = {
            "type": "payment_intent.payment_failed",
            "data": {"object": {"id": "abc123"}},
        }
        hours = HoursLineItemFactory(
            invoice=self.invoice, date_tracked=timezone.now(), quantity=2
        )
        sent_invoice = SentInvoiceFactory(
            stripe_payment_intent_id="abc123", invoice=self.invoice, total_price=200.0
        )
        hours.sent_invoice_id = sent_invoice.id
        hours.save()

        response = self.client.post(
            reverse("timary:stripe_webhook"), data={}, HTTP_STRIPE_SIGNATURE="abc123"
        )
        sent_invoice.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(sent_invoice.paid_status, SentInvoice.PaidStatus.FAILED)
        formatted_date = template_date(
            hours.date_tracked.astimezone(tz=zoneinfo.ZoneInfo("America/New_York")),
            "M j",
        )
        self.assertInHTML(
            f"""
            <div class="flex justify-between py-3 text-xl">
                <div>{floatformat(hours.quantity, -2)} hours on {formatted_date}</div>
                <div>${floatformat(hours.quantity * self.invoice.rate, -2)}</div>
            </div>
            """,
            self.extract_html_body().encode().decode("utf-8"),
        )

    @patch("timary.models.User.add_referral_discount")
    @patch("stripe.Webhook.construct_event")
    def test_stripe_webhook_trial_success(self, stripe_webhook_mock, referral_mock):
        user = UserFactory(stripe_subscription_id="abc123")
        stripe_webhook_mock.return_value = {
            "type": "invoice.created",
            "data": {"object": {"id": "abc123"}},
        }
        referral_mock.return_value = None

        self.client.force_login(user)
        response = self.client.post(
            reverse("timary:stripe_webhook"), data={}, HTTP_STRIPE_SIGNATURE="abc123"
        )

        user.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            user.stripe_subscription_status, User.StripeSubscriptionStatus.ACTIVE
        )

    @patch("stripe.Webhook.construct_event")
    @override_settings(DEBUG=True)
    def test_stripe_webhook_trial_error(self, stripe_webhook_mock):
        user = UserFactory(
            stripe_subscription_id="abc123",
            stripe_subscription_status=User.StripeSubscriptionStatus.TRIAL,
        )
        stripe_webhook_mock.return_value = {
            "type": "invoice.finalization_failed",
            "data": {"object": {"id": "abc123"}},
        }

        self.client.force_login(user)
        response = self.client.post(
            reverse("timary:stripe_webhook"), data={}, HTTP_STRIPE_SIGNATURE="abc123"
        )

        user.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            user.stripe_subscription_status, User.StripeSubscriptionStatus.INACTIVE
        )
        self.assertEqual(
            mail.outbox[0].subject, "Oops, something went wrong over here at Timary"
        )
