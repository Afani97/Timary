from django.conf import settings

from timary.models import User
from timary.utils import show_active_timer


def site_url(request):
    return {"site_url": settings.SITE_URL}


def debug_mode(request):
    return {"debug_mode": settings.DEBUG}


def random_page_title(request):
    from random import choice

    page_titles = [
        "Your time tracking solution",
        "Time tracking done right for you",
        "Accept payments for the time you've tracked",
        "Tired of invoicing for the same hours every week?",
        "Time tracking, invoicing and bookkeeping. Oh my!",
    ]
    return {"random_page_title": choice(page_titles)}


def completed_connect_account(request):
    # connect_status == 0 => Account complete
    # connect_status == 1 => Pending verifications
    # connect_status == 2 => More info needed
    if hasattr(request.user, "stripe_connect_id"):
        user_connect_reason = request.user.stripe_connect_reason
        if user_connect_reason == User.StripeConnectDisabledReasons.NONE:
            return {"connect_status": 0}
        elif user_connect_reason == User.StripeConnectDisabledReasons.PENDING:
            return {"connect_status": 1}
    return {"connect_status": 2}


def timer(request):
    if "Hx-Request" in request.headers or not request.user.is_authenticated:
        return {}
    return show_active_timer(request.user)
