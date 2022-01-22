import time

import stripe
from django.conf import settings


def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[-1].strip()
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


class StripeService:
    stripe_api_key = settings.STRIPE_SECRET_API_KEY
    stripe_public_api_key = settings.STRIPE_PUBLIC_API_KEY

    @classmethod
    def create_new_account(cls, request, user, first_token, second_token):
        stripe.api_key = cls.stripe_api_key
        stripe_connect_account = stripe.Account.create(
            country="US",
            type="custom",
            email=user.email,
            capabilities={
                "card_payments": {"requested": True},
                "transfers": {"requested": True},
            },
            business_type="individual",
            business_profile={"mcc": "1520", "url": "www.usetimary.com"},
            tos_acceptance={
                "date": int(time.time()),
                "ip": get_client_ip(request),
            },
            individual={
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
            },
        )
        stripe_customer = stripe.Customer.create(
            email=user.email,
            name=user.get_full_name(),
            stripe_account=stripe_connect_account["id"],
        )
        user.stripe_connect_id = stripe_connect_account["id"]
        user.stripe_customer_id = stripe_customer["id"]
        user.save()
        stripe.Customer.create_source(
            user.stripe_customer_id,
            source=first_token,
            stripe_account=user.stripe_connect_id,
        )
        stripe.Account.create_external_account(
            user.stripe_connect_id,
            external_account=second_token,
        )
        account_link = stripe.AccountLink.create(
            account=stripe_connect_account["id"],
            refresh_url=f"{settings.SITE_URL}/reauth",
            return_url=f"{settings.SITE_URL}/onboarding_success",
            type="account_onboarding",
        )
        return account_link["url"]

    @classmethod
    def create_payment_intent(cls):
        stripe.api_key = cls.stripe_api_key
        intent = stripe.SetupIntent.create(
            payment_method_types=["card"],
        )
        return intent["client_secret"]

    @classmethod
    def create_subscription(cls, user, delete_current=None):
        stripe.api_key = cls.stripe_api_key
        if delete_current:
            stripe.Subscription.delete(
                user.stripe_subscription_id, stripe_account=user.stripe_connect_id
            )

        product = stripe.Product.create(
            name=user.get_membership_tier_display(),
            stripe_account=user.stripe_connect_id,
        )
        price = stripe.Price.create(
            unit_amount=user.membership_tier * 100,
            currency="usd",
            recurring={"interval": "month"},
            product=product["id"],
            stripe_account=user.stripe_connect_id,
        )

        subscription = stripe.Subscription.create(
            customer=user.stripe_customer_id,
            items=[
                {"price": price["id"]},
            ],
            stripe_account=user.stripe_connect_id,
        )
        user.stripe_subscription_id = subscription["id"]
        user.save()
        return True

    @classmethod
    def get_connect_account(cls, account_id):
        stripe.api_key = cls.stripe_api_key
        return stripe.Account.retrieve(account_id)

    @classmethod
    def update_connect_account(cls, account_id):
        stripe.api_key = cls.stripe_api_key
        account_link = stripe.AccountLink.create(
            account=account_id,
            refresh_url=f"{settings.SITE_URL}/reauth",
            return_url=f"{settings.SITE_URL}/complete_connect/",
            type="account_update",
        )
        return account_link["url"]
