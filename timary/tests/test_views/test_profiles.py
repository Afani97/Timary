from unittest.mock import patch

import stripe
from django.test import override_settings
from django.urls import reverse
from django.utils.http import urlencode

from timary.forms import SMSSettingsForm
from timary.models import User
from timary.tests.factories import UserFactory
from timary.tests.test_views.basetest import BaseTest


class TestUserProfile(BaseTest):
    def setUp(self) -> None:
        super().setUp()

        self.user = UserFactory()
        self.client.force_login(self.user)

    def test_get_profile_page(self):
        response = self.client.get(reverse("timary:user_profile"))
        self.assertInHTML(
            f"""
            <h2 class="card-title">{self.user.first_name} {self.user.last_name}</h2>
            <p>{self.user.email}</p>
            <p>{self.user.phone_number}</p>
            """,
            response.content.decode("utf-8"),
        )

    def test_get_profile_page_redirect(self):
        self.client.logout()
        response = self.client.get(reverse("timary:user_profile"))
        self.assertEqual(response.status_code, 302)

    def test_get_profile_partial(self):
        rendered_template = self.setup_template(
            "partials/_profile.html", {"user": self.user}
        )
        response = self.client.get(reverse("timary:user_profile_partial"))
        self.assertHTMLEqual(rendered_template, response.content.decode())

    def test_get_profile_partial_redirect(self):
        self.client.logout()
        response = self.client.get(reverse("timary:user_profile_partial"))
        self.assertEqual(response.status_code, 302)

    def test_get_edit_profile(self):
        response = self.client.get(reverse("timary:edit_user_profile"))
        self.assertInHTML(
            f'<input type="email" name="email" value="{self.user.email}" placeholder="john@appleseed.com"'
            f'class="input input-bordered border-2 text-lg w-full placeholder-gray-500" required '
            f'id="id_email">',
            response.content.decode("utf-8"),
        )
        self.assertInHTML(
            f'<input type="text" name="first_name" value="{self.user.first_name}" placeholder="John"'
            f'class="input input-bordered border-2 text-lg w-full placeholder-gray-500" required id="id_first_name">',
            response.content.decode("utf-8"),
        )
        self.assertInHTML(
            f'<input type="text" name="last_name" value="{self.user.last_name}"'
            f'placeholder="Appleseed"'
            f'class="input input-bordered border-2 text-lg w-full placeholder-gray-500" id="id_last_name"> ',
            response.content.decode("utf-8"),
        )
        self.assertInHTML(
            f'<input type="text" name="phone_number" value="{self.user.phone_number}" placeholder="+13334445555" '
            f'class="input input-bordered border-2 text-lg w-full placeholder-gray-500" id="id_phone_number">',
            response.content.decode("utf-8"),
        )

    @patch("timary.services.stripe_service.StripeService.create_new_subscription")
    def test_update_user_profile(self, stripe_subscription_mock):
        stripe_subscription_mock.return_value = None
        data = {
            "email": "user@test.com",
            "first_name": "Test",
            "last_name": "Test",
            "phone_number": "+17742613186",
            "timezone": "America/Los_Angeles",
        }
        response = self.client.post(reverse("timary:update_user_profile"), data=data)
        self.user.refresh_from_db()
        self.assertInHTML(
            """
            <h2 class="card-title">Test Test</h2>
            <p>user@test.com</p>
            <p>+17742613186</p>
            """,
            response.content.decode("utf-8"),
        )
        self.assertEqual(response.templates[0].name, "partials/_profile.html")
        self.assertEqual(response.status_code, 200)

    def test_update_user_email_already_registered(self):
        user = UserFactory()
        data = {
            "email": user.email,
            "first_name": "Test",
            "last_name": "Test",
            "phone_number": "+14445556666",
        }
        response = self.client.post(reverse("timary:update_user_profile"), data=data)
        self.assertInHTML(
            "Email already registered!",
            response.content.decode("utf-8"),
        )
        self.assertEqual(response.status_code, 200)

    def test_update_user_redirect(self):
        self.client.logout()
        data = {
            "email": "user@test.com",
            "first_name": "Test",
            "last_name": "Test",
            "phone_number": "+13334445555",
        }
        response = self.client.post(reverse("timary:update_user_profile"), data=data)
        self.assertEqual(response.status_code, 302)

    def test_update_sms_user_subscription(self):
        url_params = {
            "phone_number_availability": "Mon",
        }
        response = self.client.put(
            reverse("timary:update_sms_settings"),
            data=urlencode(url_params),  # HTMX PUT FORM
        )
        self.user.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.templates[0].name, "partials/settings/preferences/_sms.html"
        )


class TestUserSettings(BaseTest):
    def setUp(self) -> None:
        super().setUp()

        self.user = UserFactory(phone_number_availability=["Tue"])
        self.client.force_login(self.user)

    def test_get_settings_in_profile_page(self):
        response = self.client.get(reverse("timary:user_profile"))
        self.assertInHTML(
            """
            <div class="wrapper flex justify-between">
                <div class="tooltip" data-tip="Which days do you want texted to logs hours for ">
                    <div class="text-left">SMS availability</div>
                </div>
                <a class="link text-right"
                       hx-get="/profile/settings/sms/"
                       hx-target="closest .wrapper"
                       hx-swap="outerHTML"
                       >Update</a>
            </div>
            """,
            response.content.decode("utf-8"),
        )

    def test_get_sms_settings_partial(self):
        rendered_template = self.setup_template(
            "partials/settings/preferences/_sms.html",
            {
                "settings_form": SMSSettingsForm(instance=self.user),
                "settings": self.user.settings,
            },
        )
        response = self.client.get(
            reverse("timary:settings_partial", kwargs={"setting": "sms"})
        )
        self.assertHTMLEqual(rendered_template, response.content.decode("utf-8"))

    def test_get_settings_partial_cannot_download_audit(self):
        response = self.client.get(reverse("timary:user_profile"))
        with self.assertRaises(AssertionError):
            self.assertInHTML(
                """
                <tr class="flex justify-between">
                <td>Invoice audit log </td>
                <td></td>
                <td><a href="/audit/" class="btn btn-sm">Download</a></td>
                </tr>
                """,
                response.content.decode("utf-8"),
            )

    def test_get_settings_partial_download_audit(self):
        self.client.logout()
        user = UserFactory()
        self.client.force_login(user=user)
        response = self.client.get(reverse("timary:user_profile"))
        self.assertInHTML(
            """
            <div>Invoice audit log </div>
            <div></div>
            <a href="/audit/" class="btn btn-sm">Download</a>
            """,
            response.content.decode("utf-8"),
        )
        self.client.logout()
        self.client.force_login(user=self.user)

    def test_get_edit_sms_settings(self):
        response = self.client.get(reverse("timary:update_sms_settings"))
        for index, day in enumerate(User.WEEK_DAYS):
            with self.subTest(f"Testing {day[0]}"):
                self.assertInHTML(
                    day[0],
                    response.content.decode("utf-8"),
                )
        self.assertEqual(
            response.templates[0].name, "partials/settings/preferences/_edit_sms.html"
        )
        self.assertEqual(response.status_code, 200)

    def test_update_sms_settings(self):
        url_params = [
            ("phone_number_availability", "Mon"),
            ("phone_number_availability", "Tue"),
        ]
        response = self.client.put(
            reverse("timary:update_sms_settings"),
            data=urlencode(url_params),  # HTMX PUT FORM
        )

        self.user.refresh_from_db()
        self.assertEqual(self.user.phone_number_availability, ["Mon", "Tue"])
        self.assertEqual(
            response.templates[0].name, "partials/settings/preferences/_sms.html"
        )
        self.assertEqual(response.status_code, 200)

    def test_get_profile_partial_redirect(self):
        self.client.logout()
        response = self.client.get(
            reverse("timary:settings_partial", kwargs={"setting": "sms"})
        )
        self.assertEqual(response.status_code, 302)

    def test_update_settings_redirect(self):
        self.client.logout()
        url_params = [
            ("phone_number_availability", "Mon"),
            ("phone_number_availability", "Tue"),
        ]
        response = self.client.put(
            reverse("timary:update_sms_settings"),
            data=urlencode(url_params),  # HTMX PUT FORM
        )
        self.assertEqual(response.status_code, 302)

    def test_update_password_settings(self):
        user = UserFactory()
        url_params = [
            ("current_password", "Apple101!"),
            ("new_password", "NewPassword1!"),
        ]
        self.client.force_login(user)
        response = self.client.put(
            reverse("timary:update_user_password"),
            data=urlencode(url_params),  # HTMX PUT FORM
        )

        user.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(user.check_password("NewPassword1!"))

    @patch("timary.services.stripe_service.StripeService.create_payment_intent")
    @patch("timary.services.stripe_service.StripeService.update_payment_method")
    def test_update_payment_method_settings_success(
        self, update_payment_mock, create_payment_mock
    ):
        update_payment_mock.return_value = True
        create_payment_mock.return_value = None

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("timary:update_payment_method_settings"),
            {"first_token": "abc123", "second_token": "abc123"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed("partials/settings/account/_payment_method.html")
        self.assertIn(
            "Successfully updated debit card.", response.headers["HX-Trigger"]
        )

    @patch("timary.services.stripe_service.StripeService.create_payment_intent")
    @patch("timary.services.stripe_service.StripeService.update_payment_method")
    def test_update_payment_method_settings_stripe_error(
        self, update_payment_mock, create_payment_mock
    ):
        update_payment_mock.return_value = False
        create_payment_mock.return_value = None

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("timary:update_payment_method_settings"),
            {"first_token": "abc123", "second_token": "abc123"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed("partials/settings/account/_edit_payment_method.html")
        self.assertIn(
            "Error updating payment method, please try again.",
            response.content.decode("utf-8"),
        )

    @patch("timary.services.stripe_service.StripeService.create_payment_intent")
    @patch("timary.services.stripe_service.StripeService.update_payment_method")
    @override_settings(DEBUG=True)
    def test_update_payment_method_settings_card_error(
        self, update_payment_mock, create_payment_mock
    ):
        create_payment_mock.return_value = None
        update_payment_mock.return_value = False
        update_payment_mock.side_effect = stripe.error.InvalidRequestError(
            "Debit card is needed here!", None
        )

        response = self.client.post(
            reverse("timary:update_payment_method_settings"),
            {"first_token": "abc123", "second_token": "abc123"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed("partials/settings/account/_edit_payment_method.html")
        self.assertIn(
            "Error updating payment method, please try again.",
            response.content.decode("utf-8"),
        )

    @patch("timary.services.stripe_service.StripeService.readd_subscription")
    def test_update_subscription_success(self, add_subscription_mock):
        add_subscription_mock.return_value = True

        response = self.client.get(
            f'{reverse("timary:update_subscription")}?action=add'
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed("partials/settings/account/_cancel_subscription.html")
        self.assertIn(
            "Hooray! We're happy you're back!",
            response.headers["HX-Trigger"],
        )

    @patch("timary.services.stripe_service.StripeService.cancel_subscription")
    def test_update_subscription_error(self, cancel_subscription_mock):
        cancel_subscription_mock.return_value = True

        response = self.client.get(
            f'{reverse("timary:update_subscription")}?action=cancel'
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed("partials/settings/account/_add_subscription.html")
        self.assertIn(
            "We're sorry to see you go.",
            response.headers["HX-Trigger"],
        )
