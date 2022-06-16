import datetime
import os
from contextlib import contextmanager

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import tag
from django.urls import reverse
from playwright.sync_api import sync_playwright

from timary.models import User
from timary.tests.factories import DailyHoursFactory, InvoiceFactory, UserFactory


class BaseUITest(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
        super().setUpClass()
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.webkit.launch(headless=settings.HEADLESS_UI)

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
        page.click('button:has-text("Login")')
        try:
            yield page
        finally:
            page.close()


class TestUI(BaseUITest):
    @tag("ui")
    def test_login_for_first_time_view_welcome_invoice_page(self):
        with self.start_test(UserFactory()) as page:
            page.wait_for_selector("#intro-text", timeout=2000)
            self.assertEqual(page.inner_text("#intro-text"), "Hello there")

    @tag("ui")
    def test_create_first_invoice(self):
        with self.start_test(UserFactory()) as page:
            page.wait_for_selector("#intro-text", timeout=2000)
            page.fill("#id_title", "Timary")
            page.fill("#id_hourly_rate", "100")
            page.fill("#id_email_recipient_name", "John Smith")
            page.fill("#id_email_recipient", "john@smith.com")
            page.click('button:has-text("Add new invoice")')
            page.wait_for_selector("#dashboard-title", timeout=2000)
            self.assertEqual(page.inner_text("#dashboard-title"), "Dashboard")

    @tag("ui")
    def test_log_first_hours(self):
        invoice = InvoiceFactory()
        with self.start_test(invoice.user) as page:
            page.wait_for_selector("#dashboard-title", timeout=2000)
            page.click("#log_hours_btn")
            page.wait_for_selector("#new-hours-form", timeout=2000)
            page.fill("#id_hours", "2")
            page.click('button:has-text("Add new hours")')
            page.wait_for_selector("#hours-list li", timeout=2000)
            self.assertEqual(page.inner_text(".stat-value"), "2.00")

    @tag("ui")
    def test_log_first_hours_time_format(self):
        invoice = InvoiceFactory()
        with self.start_test(invoice.user) as page:
            page.wait_for_selector("#dashboard-title", timeout=2000)
            page.click("#log_hours_btn")
            page.wait_for_selector("#new-hours-form", timeout=2000)
            page.fill("#id_hours", ":25")
            page.click('button:has-text("Add new hours")')
            page.wait_for_selector("#hours-list li", timeout=2000)
            self.assertEqual(page.inner_text(".stat-value"), "0.41")

    @tag("ui")
    def test_edit_hours(self):
        hours = DailyHoursFactory()
        with self.start_test(hours.invoice.user) as page:
            page.wait_for_selector("#dashboard-title", timeout=2000)
            page.click('a:has-text("Edit")')
            page.wait_for_selector('button:has-text("Update hours")', timeout=2000)
            page.fill("#hours-list #id_hours", "2")
            page.click('button:has-text("Update hours")')
            page.wait_for_selector("#hours-list li", timeout=2000)
            self.assertEqual(page.inner_text(".stat-value"), "2.00")

    @tag("ui")
    def test_edit_invoice(self):
        invoice = InvoiceFactory()
        with self.start_test(invoice.user) as page:
            page.goto(f'{self.live_server_url}{reverse("timary:manage_invoices")}')
            page.wait_for_selector("#current-invoices", timeout=2000)
            page.click('a:has-text("Edit")')
            page.wait_for_selector('button:has-text("Update invoice")', timeout=2000)
            page.fill("#id_title", "Timary 2")
            page.fill("#id_hourly_rate", "100")
            page.fill("#id_email_recipient_name", "John Smith")
            page.fill("#id_email_recipient", "john@smith.com")
            page.click('button:has-text("Update invoice")')
            page.wait_for_selector(".card-title", timeout=2000)
            self.assertEqual(page.inner_text(".card-title"), "Timary 2 - Rate: $100")

    @tag("ui")
    def test_edit_hours_within_invoice(self):
        invoice = InvoiceFactory(
            next_date=datetime.date.today() + datetime.timedelta(days=1),
            user__membership_tier=User.MembershipTier.BUSINESS,
        )
        DailyHoursFactory(
            invoice=invoice,
            date_tracked=datetime.date.today() - datetime.timedelta(days=1),
        )
        with self.start_test(invoice.user) as page:
            page.goto(f'{self.live_server_url}{reverse("timary:manage_invoices")}')
            page.wait_for_selector("#current-invoices", timeout=2000)
            page.click('input[type="checkbox"]')
            page.wait_for_selector(".modal-button", timeout=2000)
            page.click(".modal-button")
            page.wait_for_selector(
                'h3:has-text("Update hours for this invoice period")', timeout=3000
            )
            page.fill("#id_hours", ":30")
            page.click('button:has-text("Update")')
            page.wait_for_selector(".text-success", timeout=2000)
            self.assertEqual(
                page.inner_text(".text-success"), "Successfully updated hours"
            )

    @tag("ui")
    def test_edit_profile(self):
        with self.start_test(UserFactory()) as page:
            page.goto(f'{self.live_server_url}{reverse("timary:user_profile")}')
            page.wait_for_selector("#profile", timeout=2000)
            page.click('button:has-text("Edit profile")')
            page.wait_for_selector('button:has-text("Update profile")', timeout=2000)
            page.fill("#id_first_name", "John")
            page.fill("#id_last_name", "Smith")
            page.fill("#id_email", "john@smith.com")
            page.fill("#id_phone_number", "+17742613186")
            page.click('button:has-text("Update profile")')
            page.wait_for_selector('button:has-text("Edit profile")', timeout=2000)
            self.assertEqual(page.inner_text(".card-title"), "John Smith")

    @tag("ui")
    def test_logout(self):
        hours = DailyHoursFactory()
        with self.start_test(hours.invoice.user) as page:
            page.goto(f'{self.live_server_url}{reverse("timary:index")}')
            page.wait_for_selector("#dashboard-title", timeout=2000)
            page.click('a:has-text("Logout")')
            page.wait_for_selector('button:has-text("Login")', timeout=2000)
            self.assertEqual(page.inner_text("h1"), "Login")
