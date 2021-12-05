from django.test import Client, TestCase
from django.urls import reverse

from timary.tests.factories import UserFactory


class TestAuthViews(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = UserFactory()

    def test_login(self):
        response = self.client.post(
            reverse("timary:login"),
            {"email": self.user.email, "password": "Apple101!"},
        )
        self.assertEquals(response.status_code, 302)
        self.assertEquals(response.url, reverse("timary:index"))

    def test_login_failed(self):
        response = self.client.post(
            reverse("timary:login"), {"email": "user@test.com", "password": "pass"}
        )
        self.assertEquals(response.status_code, 400)

    def test_signup(self):
        response = self.client.post(
            reverse("timary:register"),
            {
                "first_name": "Thomas",
                "email": "thomas@test.com",
                "password": "Apple101!",
            },
        )
        self.assertEquals(response.status_code, 302)
        self.assertEquals(response.url, reverse("timary:index"))

    def test_signup_error(self):
        response = self.client.post(
            reverse("timary:register"),
            {
                "first_name": "Thomas",
                "email": "thomas2",
                "password": "Apple101!",
            },
        )
        self.assertEquals(response.status_code, 400)

    def test_logout(self):
        self.client.post(
            reverse("timary:login"),
            {"email": self.user.email, "password": "Apple101"},
        )

        response = self.client.get(reverse("timary:logout"))

        self.assertEquals(response.status_code, 302)
        self.assertEquals(response.url, "/login/?next=/logout/")

    def test_logout_failed_redirect(self):
        response = self.client.get(reverse("timary:logout"))

        self.assertEquals(response.status_code, 302)
        self.assertEquals(response.url, "/login/?next=/logout/")
