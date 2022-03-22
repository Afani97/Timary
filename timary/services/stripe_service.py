import time

import stripe
from django.conf import settings

from timary.models import User


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
    def get_product_id(cls, user):
        if user.membership_tier == User.MembershipTier.STARTER:
            return settings.STRIPE_STARTER_ID
        if user.membership_tier == User.MembershipTier.PROFESSIONAL:
            return settings.STRIPE_PROFESSIONAL_ID
        if user.membership_tier == User.MembershipTier.BUSINESS:
            return settings.STRIPE_BUSINESS_ID

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
        )
        stripe_connect_id = stripe_connect_account["id"]
        stripe_customer_id = stripe_customer["id"]
        stripe.Customer.create_source(
            stripe_customer_id,
            source=first_token,
        )
        stripe.Account.create_external_account(
            stripe_connect_id,
            external_account=second_token,
        )
        account_link = stripe.AccountLink.create(
            account=stripe_connect_id,
            refresh_url=f"{settings.SITE_URL}/reauth",
            return_url=f"{settings.SITE_URL}/onboarding_success",
            type="account_onboarding",
        )
        return stripe_connect_id, stripe_customer_id, account_link["url"]

    @classmethod
    def create_payment_intent(cls):
        stripe.api_key = cls.stripe_api_key
        intent = stripe.SetupIntent.create(
            payment_method_types=["card"],
        )
        return intent["client_secret"]

    @classmethod
    def update_payment_method(cls, user, first_token, second_token):
        stripe.api_key = cls.stripe_api_key
        customer_source = stripe.Customer.create_source(
            user.stripe_customer_id,
            source=first_token,
        )
        _ = stripe.Customer.modify(
            user.stripe_customer_id,
            default_source=customer_source["id"],
        )
        connect_source = stripe.Account.create_external_account(
            user.stripe_connect_id,
            external_account=second_token,
            default_for_currency=True,
        )
        return customer_source and connect_source

    @classmethod
    def create_payment_intent_for_payout(cls, sent_invoice):
        stripe.api_key = cls.stripe_api_key
        application_fee = 0
        if sent_invoice.user.membership_tier == User.MembershipTier.INVOICE_FEE:
            application_fee = int(sent_invoice.total_price)
        intent = stripe.PaymentIntent.create(
            payment_method_types=["card"],
            amount=int(sent_invoice.total_price * 100),
            currency="usd",
            application_fee_amount=application_fee,
            transfer_data={
                "destination": sent_invoice.user.stripe_connect_id,
            },
        )
        return intent["client_secret"]

    @classmethod
    def create_subscription(cls, user, delete_current=None):
        stripe.api_key = cls.stripe_api_key

        if delete_current and user.stripe_subscription_id:
            if stripe.Subscription.retrieve(user.stripe_subscription_id):
                stripe.Subscription.delete(user.stripe_subscription_id)

        if user.membership_tier == User.MembershipTier.INVOICE_FEE:
            user.stripe_subscription_id = None
            user.save()
            return

        subscription = stripe.Subscription.create(
            customer=user.stripe_customer_id,
            items=[
                {"price": StripeService.get_product_id(user)},
            ],
        )
        user.stripe_subscription_id = subscription["id"]
        user.save()

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

    @classmethod
    def close_stripe_account(cls, user):
        stripe.api_key = cls.stripe_api_key
        if user.stripe_subscription_id and stripe.Subscription.retrieve(
            user.stripe_subscription_id
        ):
            sub = stripe.Subscription.delete(user.stripe_subscription_id)
            return sub is not None
