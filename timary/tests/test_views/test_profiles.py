from django.urls import reverse
from django.utils.http import urlencode

from timary.tests.factories import UserProfilesFactory
from timary.tests.test_views.basetest import BaseTest


class TestUserProfiles(BaseTest):
    def setUp(self) -> None:
        super().setUp()

        self.profile = UserProfilesFactory()
        self.client.force_login(self.profile.user)

    def test_get_profile_page(self):
        response = self.client.get(reverse("timary:user_profile"))
        self.assertContains(
            response,
            f"""
        <h2 class="card-title text-center">{self.profile.user.first_name} {self.profile.user.last_name}</h2>
        <p class="text-center">{self.profile.user.email}</p>
        <p class="text-center">{self.profile.phone_number}</p>""",
        )

    def test_get_profile_page_redirect(self):
        self.client.logout()
        response = self.client.get(reverse("timary:user_profile"))
        self.assertEqual(response.status_code, 302)

    def test_get_profile_partial(self):
        rendered_template = self.setup_template(
            "partials/_profile.html", {"profile": self.profile}
        )
        response = self.client.get(reverse("timary:user_profile_partial"))
        self.assertHTMLEqual(rendered_template, response.content.decode())

    def test_get_profile_partial_redirect(self):
        self.client.logout()
        response = self.client.get(reverse("timary:user_profile_partial"))
        self.assertEqual(response.status_code, 302)

    def test_get_edit_profile(self):
        response = self.client.get(reverse("timary:edit_user_profile"))
        self.assertContains(
            response,
            f'<input type="email" name="email" value="{self.profile.user.email}" '
            f'class="input input-bordered w-full" required id="id_email">',
        )
        self.assertContains(
            response,
            f'<input type="text" name="first_name" value="{self.profile.user.first_name}" '
            f'class="input input-bordered w-full" required id="id_first_name">',
        )
        self.assertContains(
            response,
            f'<input type="text" name="last_name" value="{self.profile.user.last_name}" '
            f'placeholder="Appleseed" maxlength="150" '
            f'class="input input-bordered w-full" id="id_last_name">',
        )
        self.assertContains(
            response,
            f'<input type="text" name="phone_number" value="{self.profile.phone_number}" placeholder="+13334445555" '
            f'class="input input-bordered w-full" id="id_phone_number">',
        )

    def test_update_user_profile(self):
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
        self.profile.refresh_from_db()
        self.assertContains(
            response,
            """
        <h2 class="card-title text-center">Test Test</h2>
        <p class="text-center">user@test.com</p>
        <p class="text-center">+13334445555</p>""",
        )
        self.assertEqual(response.templates[0].name, "partials/_profile.html")
        self.assertEqual(response.status_code, 200)

    def test_update_user_profile_email_already_registered(self):
        profile = UserProfilesFactory()
        url_params = {
            "email": profile.user.email,
            "first_name": "Test",
            "last_name": "Test",
            "phone_number": "+14445556666",
        }
        response = self.client.put(
            reverse("timary:update_user_profile"),
            data=urlencode(url_params),  # HTMX PUT FORM
        )
        self.assertContains(
            response,
            f"""
                    <input type="email" name="email" value="{profile.user.email}"
                    class="input input-bordered w-full" required id="id_email">

                        <div class="text-red-600">
                            <strong>Email already registered!</strong>
                        </div>
            """,
            html=True,
        )
        self.assertEqual(response.templates[0].name, "partials/_htmx_put_form.html")
        self.assertEqual(response.status_code, 200)

    def test_update_user_profile_redirect(self):
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
