from django.urls import reverse
from django.utils.http import urlencode

from timary.tests.factories import UserFactory
from timary.tests.test_views.basetest import BaseTest


class TestUsers(BaseTest):
    def setUp(self) -> None:
        super().setUp()

        self.user = UserFactory()
        self.client.force_login(self.user)

    def test_get_profile_page(self):
        response = self.client.get(reverse("timary:user_profile"))
        self.assertContains(
            response,
            f"""
        <h2 class="card-title text-center">{self.user.first_name} {self.user.last_name}</h2>
        <p class="text-center">{self.user.email}</p>
        <p class="text-center">{self.user.phone_number}</p>""",
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
        self.assertContains(
            response,
            f'<input type="email" name="email" value="{self.user.email}" '
            f'class="input input-bordered w-full" required id="id_email">',
        )
        self.assertContains(
            response,
            f'<input type="text" name="first_name" value="{self.user.first_name}" '
            f'class="input input-bordered w-full" required id="id_first_name">',
        )
        self.assertContains(
            response,
            f'<input type="text" name="last_name" value="{self.user.last_name}" '
            f'placeholder="Appleseed" maxlength="150" '
            f'class="input input-bordered w-full" id="id_last_name">',
        )
        self.assertContains(
            response,
            f'<input type="text" name="phone_number" value="{self.user.phone_number}" placeholder="+13334445555" '
            f'class="input input-bordered w-full" id="id_phone_number">',
        )

    def test_update_user_profile(self):
        url_params = {
            "email": "user@test.com",
            "first_name": "Test",
            "last_name": "Test",
            "phone_number": "+17742613186",
        }
        response = self.client.put(
            reverse("timary:update_user_profile"),
            data=urlencode(url_params),  # HTMX PUT FORM
        )
        self.user.refresh_from_db()
        self.assertContains(
            response,
            """
        <h2 class="card-title text-center">Test Test</h2>
        <p class="text-center">user@test.com</p>
        <p class="text-center">+17742613186</p>""",
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
        self.assertContains(
            response,
            f"""
                    <input type="email" name="email" value="{user.email}"
                    class="input input-bordered w-full" required id="id_email">

                        <div class="text-red-600">
                            <strong>Email already registered!</strong>
                        </div>
            """,
            html=True,
        )
        self.assertEqual(response.templates[0].name, "partials/_htmx_put_form.html")
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
