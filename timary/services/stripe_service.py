import datetime
import sys
import time

import stripe
from django.conf import settings
from django.utils import timezone
from django_q.tasks import schedule

from timary.services.email_service import EmailService


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
    def frontend_ui(cls):
        return {
            "style": {
                "base": {
                    "iconColor": "#c4f0ff",
                    "color": "#fff",
                    "fontWeight": "500",
                    "fontFamily": "Roboto, Open Sans, Segoe UI, sans-serif",
                    "fontSize": "16px",
                    "fontSmoothing": "antialiased",
                    ":-webkit-autofill": {
                        "color": "#fce883",
                    },
                },
                "invalid": {
                    "iconColor": "#ff5724",
                    "color": "#ff5724",
                },
            },
            "classes": {"base": "input input-bordered border-2 text-lg px-2 py-3"},
        }

    @classmethod
    def get_price_id(cls):
        return settings.STRIPE_PRICE_ID

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
                "us_bank_account_ach_payments": {"requested": True},
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
        user.stripe_subscription_recurring_price = 29
        user.save()
        return stripe_connect_id, stripe_customer_id

    @classmethod
    def create_customer_for_invoice(cls, invoice):
        stripe.api_key = cls.stripe_api_key
        stripe_customer = stripe.Customer.create(
            email=invoice.email_recipient,
            name=invoice.email_recipient_name,
        )
        invoice.email_recipient_stripe_customer_id = stripe_customer["id"]
        invoice.save()

    @classmethod
    def retrieve_customer(cls, customer_id):
        stripe.api_key = cls.stripe_api_key
        stripe_customer = stripe.Customer.retrieve(customer_id)
        return stripe_customer

    @classmethod
    def retrieve_customer_payment_method(cls, customer_id):
        stripe.api_key = cls.stripe_api_key
        payment_methods = stripe.Customer.list_payment_methods(
            customer_id, type="us_bank_account"
        )
        if len(payment_methods["data"]) > 0:
            return payment_methods["data"][0]
        return None

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
    def calculate_application_fee(cls, sent_invoice):
        # Add $5 ACH Debit Fee
        application_fee = 500
        invoice_amount = (
            int(sent_invoice.total_price * 100) + 500
        )  # Add $5 ACH Debit Fee
        return application_fee, invoice_amount

    @classmethod
    def create_payment_intent_for_payout(cls, sent_invoice):
        stripe.api_key = cls.stripe_api_key
        application_fee, invoice_amount = StripeService.calculate_application_fee(
            sent_invoice
        )
        intent = stripe.PaymentIntent.create(
            payment_method_types=["us_bank_account"],
            customer=sent_invoice.invoice.email_recipient_stripe_customer_id,
            amount=invoice_amount,
            setup_future_usage="off_session",
            currency="usd",
            application_fee_amount=application_fee,
            transfer_data={
                "destination": sent_invoice.user.stripe_connect_id,
            },
        )
        return intent

    @classmethod
    def confirm_payment(cls, sent_invoice):
        stripe.api_key = cls.stripe_api_key
        application_fee, invoice_amount = StripeService.calculate_application_fee(
            sent_invoice
        )

        # Retrieve the first bank account for invoicee and confirm the payment.
        invoicee_payment_method = StripeService.retrieve_customer_payment_method(
            sent_invoice.invoice.email_recipient_stripe_customer_id
        )

        intent = stripe.PaymentIntent.create(
            payment_method_types=["us_bank_account"],
            payment_method=invoicee_payment_method["id"],
            customer=sent_invoice.invoice.email_recipient_stripe_customer_id,
            amount=invoice_amount,
            confirm=True,
            currency="usd",
            application_fee_amount=application_fee,
            transfer_data={
                "destination": sent_invoice.user.stripe_connect_id,
            },
        )
        return intent

    @classmethod
    def create_new_subscription(cls, user):
        from timary.models import User

        stripe.api_key = cls.stripe_api_key

        subscription = stripe.Subscription.create(
            customer=user.stripe_customer_id,
            items=[
                {"price": StripeService.get_price_id()},
            ],
            trial_period_days=30,  # 30 day free trial
        )
        user.stripe_subscription_id = subscription["id"]
        user.save()

        if user.referrer_id:
            referred_user = User.objects.get(referral_id=user.referral_id)
            if referred_user:
                referred_user.add_referral_discount()

        # Send trial reminders for 14, 7, 2, 1 days left
        days_of_notice = [16, 23, 28, 29]
        today = timezone.now()
        for day in days_of_notice:
            days_left = 30 - day
            _ = schedule(
                "timary.services.email_service.EmailService.send_plain",
                f"Timary free trial ending in {days_left} day{'s' if day > 1 else ''}.",
                f"""
Hello {user.first_name.capitalize()},

Just wanted to give you a heads up that the free trial for Timary ends in {days_left} day{'s' if day > 1 else ''}.

If you feel that Timary isn't a good fit, we're sorry to hear that.
Please go to your account and cancel the subscription if you don't need Timary's services any longer.

Otherwise, keep as you are.

Thanks again,
Aristotel
ari@usetimary.com
                """,
                user.email,
                schedule_type="O",
                next_run=today + datetime.timedelta(days=day),
            )

    @classmethod
    def readd_subscription(cls, user):
        """Difference from create_new_subscription is no trial"""
        from timary.models import User

        stripe.api_key = cls.stripe_api_key

        try:
            subscription = stripe.Subscription.create(
                customer=user.stripe_customer_id,
                items=[
                    {"price": StripeService.get_price_id()},
                ],
            )
        except stripe.error.InvalidRequestError as e:
            print(
                f"Subscription failed to re-add: user_id={user.id}. stripe error={str(e)}",
                file=sys.stderr,
            )
            return False
        user.stripe_subscription_id = subscription["id"]
        user.stripe_subscription_status = User.StripeSubscriptionStatus.ACTIVE
        user.save()
        if user.referrer_id:
            referred_user = User.objects.get(referral_id=user.referral_id)
            if referred_user:
                referred_user.add_referral_discount()
        return True

    @classmethod
    def get_connect_account(cls, account_id):
        stripe.api_key = cls.stripe_api_key
        return stripe.Account.retrieve(account_id)

    @classmethod
    def get_subscription(cls, subscription_id):
        stripe.api_key = cls.stripe_api_key
        return stripe.Subscription.retrieve(subscription_id)

    @classmethod
    def cancel_subscription(cls, user):
        from timary.models import User

        stripe.api_key = cls.stripe_api_key
        try:
            stripe.Subscription.delete(user.stripe_subscription_id)
        except stripe.error.InvalidRequestError as e:
            print(
                f"Subscription failed to cancel: user_id={user.id}. stripe error={str(e)}",
                file=sys.stderr,
            )
            return False
        user.stripe_subscription_status = User.StripeSubscriptionStatus.INACTIVE
        user.stripe_subscription_id = None
        user.stripe_subscription_recurring_price = 29
        user.save()

        EmailService.send_plain(
            "No one likes a breakup.",
            f"""
Hi {user.first_name.capitalize()},

We're saddened that Timary wasn't the right fit.

If you have a minute, can you please reply with a quick message what Timary lacked that you wished was supported.


Hope to see you again,
Aristotel
ari@usetimary.com
            """,
            user.email,
        )

    @classmethod
    def update_connect_account(cls, user_id, account_id):
        stripe.api_key = cls.stripe_api_key
        account_link = stripe.AccountLink.create(
            account=account_id,
            refresh_url=f"{settings.SITE_URL}/update_connect/",
            return_url=f"{settings.SITE_URL}/complete_connect?user_id={user_id}",
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

    @classmethod
    def get_amount_off_subscription(cls, user):
        subscription = StripeService.get_subscription(user.stripe_subscription_id)
        if subscription["discount"]:
            return int(subscription["discount"]["coupon"]["amount_off"] / 100), True
        return 0, False

    @classmethod
    def create_subscription_discount(cls, user, amount, discount_to_delete=None):
        stripe.api_key = cls.stripe_api_key
        if discount_to_delete:
            stripe.Subscription.delete_discount(discount_to_delete)
        coupon = stripe.Coupon.create(
            amount_off=amount, duration="forever", max_redemptions=1, currency="usd"
        )

        subscription = stripe.Subscription.modify(
            user.stripe_subscription_id,
            coupon=coupon["id"],
        )

        new_sub_cost = user.stripe_subscription_recurring_price - (amount / 100)
        user.stripe_subscription_recurring_price = new_sub_cost
        user.save()
        EmailService.send_plain(
            "Good news! You're saving money!",
            f"""
Hey {user.first_name},

Someone you referred Timary to has registered using your invite!

So you know what that means, you're monthly subscription is now lowered to: ${new_sub_cost}

If you don't want this to change, let us know and we can revert it if you'd like. (Why would you?)


Best,
Aristotel F
Timary LLC
                                """,
            user.email,
        )

        return subscription["id"]
