from django.conf import settings

from timary.models import User


def site_url(request):
    return {"site_url": settings.SITE_URL}


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
