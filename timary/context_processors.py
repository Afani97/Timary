from django.conf import settings


def site_url(request):
    return {"site_url": settings.SITE_URL}


def completed_connect_account(request):
    if hasattr(request.user, "stripe_connect_id"):
        return {"completed_connect_account": request.user.stripe_payouts_enabled}
    else:
        return {"completed_connect_account": False}
