from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse

from timary.tests.factories import UserFactory


class TestAuthViews(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = UserFactory()
        self.STRIPE_REDIRECT = "https://connect.stripe.com"

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

    @patch("timary.services.stripe_service.StripeService.create_new_account")
    def test_signup(self, stripe_create_mock):
        stripe_create_mock.return_value = self.STRIPE_REDIRECT
        response = self.client.post(
            reverse("timary:register"),
            {
                "full_name": "Bruce Wayne",
                "email": "bwayen@test.com",
                "password": "Apple101!",
                "membership_tier": "5",
                "first_token": "token_1",
                "second_token": "token_2",
            },
        )
        self.assertEquals(response.status_code, 302)
        self.assertEquals(response.url, self.STRIPE_REDIRECT)

    @patch("timary.services.stripe_service.StripeService.create_payment_intent")
    @patch("timary.services.stripe_service.StripeService.create_new_account")
    def test_signup_error(self, stripe_create_mock, stripe_intent_mock):
        stripe_create_mock.return_value = self.STRIPE_REDIRECT
        stripe_intent_mock.return_value = "abc123"
        response = self.client.post(
            reverse("timary:register"),
            {
                "full_name": "Bruce Wayne",
                "email": "thomas2",
                "password": "Apple101!",
                "membership_tier": "5",
                "first_token": "token_1",
                "second_token": "token_2",
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
