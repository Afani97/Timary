import os
import uuid
from contextlib import contextmanager
from unittest.mock import patch

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings, tag
from django.urls import reverse
from django.utils import timezone
from playwright.sync_api import sync_playwright

from timary.tests.factories import (
    ClientFactory,
    HoursLineItemFactory,
    IntervalInvoiceFactory,
    SentInvoiceFactory,
    UserFactory,
)


@override_settings(DEBUG=True)
class BaseUITest(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
        os.environ["DEBUG"] = "True"
        super().setUpClass()
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.webkit.launch(
            headless=settings.HEADLESS_UI, slow_mo=100
        )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.browser.close()
        cls.playwright.stop()

    @contextmanager
    def start_test(cls, user):
        page = cls.browser.new_page()
        page.goto(f'{cls.live_server_url}{reverse("timary:login")}')
        page.fill("#id_email", user.email)
        page.fill("#id_password", "Apple101!")
        page.click('button:has-text("Continue")')
        try:
            yield page
        finally:
            page.close()


class TestUI(BaseUITest):
    @tag("ui")
    @patch("timary.models.User.onboard_user")
    @patch("timary.services.stripe_service.StripeService.create_new_account")
    def test_register_account(self, stripe_new_mock, onboard_user_mock):
        stripe_new_mock.return_value = "abc123", "abc123"
        onboard_user_mock.return_value = None
        page = self.browser.new_page()

        page.goto(f'{self.live_server_url}{reverse("timary:register")}')
        page.fill("#id_full_name", "John Smith", timeout=1000)
        page.fill("#id_email", f"john+{uuid.uuid4()}@test.com")
        page.fill("#id_password", "Apple101!")

        stripe_frame = page.frame_locator("iframe").first
        stripe_frame.locator('[placeholder="Card number"]').fill("4000056655665556")
        stripe_frame.locator('[placeholder="MM / YY"]').fill("04/30")
        stripe_frame.locator('[placeholder="CVC"]').fill("242")
        stripe_frame.locator('[placeholder="ZIP"]').fill("10101")

        page.wait_for_timeout(100)

        page.click('button:has-text("Start Your Free Trial")')

        page.wait_for_timeout(1000)

        self.assertIsNotNone(page.locator("h1", has_text="Your current invoices").first)

        page.close()

    @tag("ui")
    @patch("timary.services.stripe_service.StripeService.create_customer_for_invoice")
    def test_create_first_invoice(self, stripe_customer_mock):
        stripe_customer_mock.return_value = None
        user = UserFactory()
        client = ClientFactory(user=user)
        with self.start_test(user) as page:
            page.goto(f'{self.live_server_url}{reverse("timary:manage_invoices")}')
            page.wait_for_selector("#intro-text", timeout=2000)
            page.click("#new-interval")
            page.wait_for_selector("#id_title", timeout=2000)
            page.fill("#id_title", "Timary")
            page.fill("#id_rate", "100")
            client_label = f"{client.name} - {client.email}"
            page.get_by_label("Client:").select_option(label=client_label)
            page.click('button:has-text("Add new invoice")')
            page.wait_for_selector("#dashboard-title", timeout=2000)
            self.assertEqual(page.inner_text("#dashboard-title"), "Dashboard")

    @tag("ui")
    @patch("timary.services.stripe_service.StripeService.create_customer_for_invoice")
    def test_create_first_invoice_milestone(self, stripe_customer_mock):
        stripe_customer_mock.return_value = None
        user = UserFactory()
        client = ClientFactory(user=user)
        with self.start_test(user) as page:
            page.goto(f'{self.live_server_url}{reverse("timary:manage_invoices")}')
            page.wait_for_selector("#intro-text", timeout=2000)
            page.click("#new-milestone", timeout=2000)
            page.wait_for_selector("#id_title", timeout=2000)
            page.fill("#id_title", "Timary")
            page.fill("#id_rate", "100")
            page.fill("#id_milestone_total_steps", "5")
            client_label = f"{client.name} - {client.email}"
            page.get_by_label("Client:").select_option(label=client_label)
            page.click('button:has-text("Add new invoice")')
            page.wait_for_selector("#dashboard-title", timeout=2000)
            self.assertEqual(page.inner_text("#dashboard-title"), "Dashboard")

    @tag("ui")
    @patch("timary.services.stripe_service.StripeService.create_customer_for_invoice")
    def test_create_first_invoice_weekly(self, stripe_customer_mock):
        stripe_customer_mock.return_value = None
        user = UserFactory()
        client = ClientFactory(user=user)
        with self.start_test(user) as page:
            page.goto(f'{self.live_server_url}{reverse("timary:manage_invoices")}')
            page.wait_for_selector("#intro-text", timeout=2000)
            page.click("#new-weekly", timeout=2000)
            page.wait_for_selector("#id_title", timeout=2000)
            page.fill("#id_title", "Timary")
            page.fill("#id_rate", "100")
            client_label = f"{client.name} - {client.email}"
            page.get_by_label("Client:").select_option(label=client_label)
            page.click('button:has-text("Add new invoice")')
            page.wait_for_selector("#dashboard-title", timeout=2000)
            self.assertEqual(page.inner_text("#dashboard-title"), "Dashboard")

    @tag("ui")
    def test_log_first_hours(self):
        invoice = IntervalInvoiceFactory()
        with self.start_test(invoice.user) as page:
            page.wait_for_selector("#dashboard-title", timeout=2000)
            page.click("#log_hours_btn")
            page.wait_for_selector("#new-hours-form", timeout=2000)
            page.fill("#id_quantity", "2")
            page.get_by_label("Invoice:").select_option(label=invoice.title)
            page.click('button:has-text("Add new hours")')
            page.wait_for_selector("#hours-list li", timeout=2000)
            self.assertEqual(page.inner_text(".stat-value"), "2")

    @tag("ui")
    def test_log_first_hours_time_format(self):
        invoice = IntervalInvoiceFactory()
        with self.start_test(invoice.user) as page:
            page.wait_for_selector("#dashboard-title", timeout=2000)
            page.click("#log_hours_btn")
            page.wait_for_selector("#new-hours-form", timeout=2000)
            page.fill("#id_quantity", ":25")
            page.get_by_label("Invoice:").select_option(label=invoice.title)
            page.click('button:has-text("Add new hours")')
            page.wait_for_selector("#hours-list li", timeout=2000)
            self.assertEqual(page.inner_text(".stat-value"), "0.41")

    @tag("ui")
    def test_edit_hours(self):
        hours = HoursLineItemFactory()
        with self.start_test(hours.invoice.user) as page:
            page.wait_for_selector("#dashboard-title", timeout=2000)
            page.wait_for_selector(".edit-hours", timeout=2000).click()
            page.wait_for_selector('button:has-text("Update")', timeout=2000)
            page.fill(f"#hours-list #id_{hours.slug_id}", "2")
            page.click('button:has-text("Update")')
            page.wait_for_selector("#hours-list li", timeout=2000)
            self.assertEqual(page.inner_text(".stat-value"), "2")

    @tag("ui")
    def test_edit_invoice(self):
        user = UserFactory()
        client = ClientFactory(user=user)
        IntervalInvoiceFactory(user=user, client=client)
        with self.start_test(user) as page:
            page.goto(f'{self.live_server_url}{reverse("timary:manage_invoices")}')
            page.click(".card-body .dropdown")
            page.click('a:has-text("Edit")')
            page.wait_for_selector('button:has-text("Update")', timeout=2000)
            page.fill("#id_title", "Timary 2")
            page.fill("#id_rate", "100")
            client_label = f"{client.name} - {client.email}"
            page.get_by_label("Client:").select_option(label=client_label)
            page.click('button:has-text("Update")')
            page.wait_for_selector(".card-body h2", timeout=2000)
            self.assertEqual(page.inner_text(".card-body h2"), "Timary 2")

    @tag("ui")
    def test_edit_hours_within_invoice(self):
        invoice = IntervalInvoiceFactory(
            next_date=timezone.now() + timezone.timedelta(days=1)
        )
        hours = HoursLineItemFactory(
            invoice=invoice,
            date_tracked=timezone.now() - timezone.timedelta(days=1),
        )
        with self.start_test(invoice.user) as page:
            page.goto(f'{self.live_server_url}{reverse("timary:manage_invoices")}')
            page.click('input[type="checkbox"]')
            page.wait_for_selector(".modal-button", timeout=2000)
            page.click(".modal-button")
            page.wait_for_selector(
                'h3:has-text("Update hours for this invoice period")', timeout=3000
            )
            page.fill(f"#id_{hours.slug_id}", ":30")
            page.click('button:has-text("Update")')
            page.wait_for_selector(".text-success", timeout=2000)
            self.assertEqual(
                page.inner_text(".text-success"), "Successfully updated hours!"
            )

    @tag("ui")
    def test_edit_hours_for_sent_invoice(self):
        invoice = IntervalInvoiceFactory(
            next_date=timezone.now() + timezone.timedelta(days=1)
        )
        hours = HoursLineItemFactory(
            invoice=invoice,
            date_tracked=timezone.now() - timezone.timedelta(days=1),
        )
        sent_invoice = SentInvoiceFactory(invoice=invoice, user=invoice.user)
        hours.sent_invoice_id = sent_invoice.id
        hours.save()
        with self.start_test(invoice.user) as page:
            page.goto(f'{self.live_server_url}{reverse("timary:manage_invoices")}')
            page.click(".card-body .dropdown")
            page.click('label:has-text("View sent invoices")')
            page.wait_for_selector('h3:has-text("View sent invoices")', timeout=3000)
            page.click("span:has-text('Edit')")
            page.wait_for_selector(".edit-sent-hours", timeout=3000)
            page.fill(f"#id_{hours.slug_id}", ":30")
            page.click('button:has-text("Update")')
            page.wait_for_selector(".text-success", timeout=2000)
            self.assertEqual(
                page.inner_text(".text-success"), "Successfully updated hours!"
            )

    @tag("ui")
    def test_edit_profile(self):
        with self.start_test(UserFactory()) as page:
            page.goto(f'{self.live_server_url}{reverse("timary:user_profile")}')
            page.wait_for_selector("#profile", timeout=2000)
            page.click('button:has-text("Edit")')
            page.wait_for_selector('button:has-text("Update")', timeout=2000)
            page.fill("#id_first_name", "John")
            page.fill("#id_last_name", "Smith")
            page.fill("#id_email", "john@smith.com")
            page.fill("#id_phone_number", "+17742613186")
            page.click('button:has-text("Update")')
            page.wait_for_selector('button:has-text("Edit")', timeout=2000)
            self.assertEqual(page.inner_text(".card-title"), "John Smith")

    @tag("ui")
    def test_logout(self):
        hours = HoursLineItemFactory()
        with self.start_test(hours.invoice.user) as page:
            page.goto(f'{self.live_server_url}{reverse("timary:index")}')
            page.wait_for_selector("#dashboard-title", timeout=2000)
            page.click('a:has-text("Logout")')
            page.wait_for_selector('button:has-text("Continue")', timeout=2000)
            self.assertEqual(page.inner_text("h1"), "Login to Timary")

    @tag("ui")
    @patch("timary.services.stripe_service.StripeService.create_customer_for_invoice")
    def test_create_first_invoice_single(self, stripe_customer_mock):
        stripe_customer_mock.return_value = None
        user = UserFactory()
        client = ClientFactory(user=user)
        with self.start_test(user) as page:
            page.goto(f'{self.live_server_url}{reverse("timary:manage_invoices")}')
            page.wait_for_selector("#intro-text", timeout=2000)
            page.click("#new-single", timeout=2000)
            page.wait_for_selector("#id_title", timeout=2000)
            page.fill("#id_title", "Timary")
            client_label = f"{client.name} - {client.email}"
            page.get_by_label("Client:").select_option(label=client_label)
            page.fill("#id_description", "Test")
            page.fill("#id_quantity", "1")
            page.fill("#id_unit_price", "2.5")
            page.click('button:has-text("Create")')
            page.wait_for_selector("h1", timeout=2000)
            self.assertEqual(page.inner_text("h1"), "Update Invoice")
