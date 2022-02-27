from unittest.mock import patch

from django.urls import reverse
from django.utils.http import urlencode

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
            <h2 class="card-title text-center">{self.user.first_name} {self.user.last_name}</h2>
            <p class="text-center">{self.user.email}</p>
            <p class="text-center">{self.user.phone_number}</p>
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
            f'class="input input-bordered text-lg w-full emailinput" required '
            f'id="id_email">',
            response.content.decode("utf-8"),
        )
        self.assertInHTML(
            f'<input type="text" name="first_name" value="{self.user.first_name}" placeholder="John"'
            f'class="input input-bordered text-lg w-full textinput textInput" required id="id_first_name">',
            response.content.decode("utf-8"),
        )
        self.assertInHTML(
            f'<input type="text" name="last_name" value="{self.user.last_name}"'
            f'placeholder="Appleseed"'
            f'class="input input-bordered text-lg w-full textinput textInput" id="id_last_name"> ',
            response.content.decode("utf-8"),
        )
        self.assertInHTML(
            f'<input type="text" name="phone_number" value="{self.user.phone_number}" placeholder="+13334445555" '
            f'class="input input-bordered text-lg w-full textinput textInput" id="id_phone_number">',
            response.content.decode("utf-8"),
        )

    @patch("timary.services.stripe_service.StripeService.create_subscription")
    def test_update_user_profile(self, stripe_subscription_mock):
        stripe_subscription_mock.return_value = None
        url_params = {
            "email": "user@test.com",
            "first_name": "Test",
            "last_name": "Test",
            "phone_number": "+17742613186",
            "membership_tier": "19",
        }
        response = self.client.put(
            reverse("timary:update_user_profile"),
            data=urlencode(url_params),  # HTMX PUT FORM
        )
        self.user.refresh_from_db()
        self.assertInHTML(
            """
            <h2 class="card-title text-center">Test Test</h2>
            <p class="text-center">user@test.com</p>
            <p class="text-center">+17742613186</p>
            <p class="text-center">Current subscription: Professional</p>
            """,
            response.content.decode("utf-8"),
        )
        self.assertEqual(response.templates[0].name, "partials/_profile.html")
        self.assertEqual(response.status_code, 200)

    def test_update_user_email_already_registered(self):
        user = UserFactory()
        url_params = {
            "email": user.email,
            "first_name": "Test",
            "last_name": "Test",
            "phone_number": "+14445556666",
        }
        response = self.client.put(
            reverse("timary:update_user_profile"),
            data=urlencode(url_params),  # HTMX PUT FORM
        )
        self.assertInHTML(
            f"""
            <input type="email" name="email" value="{user.email}" placeholder="john@appleseed.com"
            class="input input-bordered text-lg w-full emailinput" required id="id_email">
            <span id="error_1_id_email" class="help-inline">
                <strong>Email already registered!</strong>
            </span>
            """,
            response.content.decode("utf-8"),
        )
        self.assertEqual(response.status_code, 200)

    def test_update_user_redirect(self):
        self.client.logout()
        url_params = {
            "email": "user@test.com",
            "first_name": "Test",
            "last_name": "Test",
            "phone_number": "+13334445555",
        }
        response = self.client.put(
            reverse("timary:update_user_profile"),
            data=urlencode(url_params),  # HTMX PUT FORM
        )
        self.assertEqual(response.status_code, 302)

    @patch("timary.services.stripe_service.StripeService.create_subscription")
    def test_update_user_subscription(self, stripe_subscription_mock):
        stripe_subscription_mock.return_value = None
        self.assertEqual(self.user.membership_tier, 19)
        url_params = {
            "email": self.user.email,
            "first_name": self.user.first_name,
            "last_name": self.user.last_name,
            "phone_number": "+17742613186",
            "membership_tier": "49",
        }
        response = self.client.put(
            reverse("timary:update_user_profile"),
            data=urlencode(url_params),  # HTMX PUT FORM
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.membership_tier, 49)
        self.assertInHTML(
            f"""
            <h2 class="card-title text-center">{self.user.get_full_name()}</h2>
            <p class="text-center">{self.user.email}</p>
            <p class="text-center">{self.user.formatted_phone_number}</p>
            <p class="text-center">Current subscription: Business</p>
            """,
            response.content.decode("utf-8"),
        )
        self.assertEqual(response.templates[0].name, "partials/_profile.html")
        self.assertEqual(response.status_code, 200)


class TestUserSettings(BaseTest):
    def setUp(self) -> None:
        super().setUp()

        self.user = UserFactory(phone_number_availability=["Tue"])
        self.client.force_login(self.user)

    def test_get_settings_in_profile_page(self):
        response = self.client.get(reverse("timary:user_profile"))
        self.assertInHTML(
            """
            <div class="form-control">
                <label class="label" for="Tue"><span class="label-text">Tue</span></label>
                <input
                    id="Tue"
                    type="checkbox"
                    class="checkbox"
                    checked="checked"
                    disabled
                >
            </div>
            """,
            response.content.decode("utf-8"),
        )

    def test_get_settings_partial(self):
        rendered_template = self.setup_template(
            "partials/_settings.html", {"settings": self.user.settings}
        )
        response = self.client.get(reverse("timary:settings_partial"))
        self.assertHTMLEqual(rendered_template, response.content.decode("utf-8"))

    def test_get_settings_partial_with_no_phone_avail(self):
        self.user.phone_number_availability = None
        self.user.save()
        self.user.refresh_from_db()
        response = self.client.get(reverse("timary:settings_partial"))
        self.assertInHTML(
            "<label>Update availability to receive texts</label>",
            response.content.decode("utf-8"),
        )

    def test_get_edit_user_settings(self):
        response = self.client.get(reverse("timary:update_user_settings"))
        for index, day in enumerate(User.WEEK_DAYS):
            with self.subTest(f"Testing {day[0]}"):
                self.assertInHTML(
                    f"""
                    <div class="form-control">
                        <label class="label" for="id_phone_number_availability_{index}">
                            <span class="label-text">{day[0]}</span>
                        </label>
                        <input
                            id="id_phone_number_availability_{index}"
                            name="phone_number_availability"
                            type="checkbox"
                            class="checkbox"
                            value="{day[0]}"
                            {'checked=checked' if day[0] in self.user.phone_number_availability else ""}
                        >
                    </div>
                    """,
                    response.content.decode("utf-8"),
                )
        self.assertEqual(response.templates[0].name, "partials/_settings_form.html")
        self.assertEqual(response.status_code, 200)

    def test_update_user_settings(self):
        url_params = [
            ("phone_number_availability", "Mon"),
            ("phone_number_availability", "Tue"),
        ]
        response = self.client.put(
            reverse("timary:update_user_settings"),
            data=urlencode(url_params),  # HTMX PUT FORM
        )
        self.user.refresh_from_db()
        for index, day in enumerate(["Mon", "Tue"]):
            with self.subTest(f"Testing {day}"):
                self.assertInHTML(
                    f"""
                    <div class="form-control">
                        <label class="label" for="{day}"><span class="label-text">{day}</span></label>
                        <input
                            id="{day}"
                            type="checkbox"
                            class="checkbox"
                            checked="checked"
                            disabled
                        >
                    </div>
                    """,
                    response.content.decode("utf-8"),
                )
        self.assertEqual(response.templates[0].name, "partials/_settings.html")
        self.assertEqual(response.status_code, 200)

    def test_get_profile_partial_redirect(self):
        self.client.logout()
        response = self.client.get(reverse("timary:settings_partial"))
        self.assertEqual(response.status_code, 302)

    def test_update_settings_redirect(self):
        self.client.logout()
        url_params = [
            ("phone_number_availability", "Mon"),
            ("phone_number_availability", "Tue"),
        ]
        response = self.client.put(
            reverse("timary:update_user_settings"),
            data=urlencode(url_params),  # HTMX PUT FORM
        )
        self.assertEqual(response.status_code, 302)
