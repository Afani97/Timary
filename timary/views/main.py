from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import F, Sum
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django_twilio.decorators import twilio_view
from django_twilio.request import decompose
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse

from timary.forms import DailyHoursForm
from timary.models import DailyHoursInput, User


def landing_page(request):
    if request.user.is_authenticated:
        return redirect(reverse("timary:index"))
    return render(request, "timary/landing_page.html", {})


def twilio(request):
    send_sms()
    return index(request)


def send_sms():
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

    _ = client.messages.create(
        to="+17742613186", from_=settings.TWILIO_PHONE_NUMBER, body="Sup bro!"
    )
    print("SENDING SMS")


@twilio_view
def twilio_reply(request):
    twilio_request = decompose(request)

    # See the Twilio attributes on the class
    print(twilio_request.to)
    print(twilio_request.from_)
    user = User.objects.get(phone_number=twilio_request.from_)

    r = MessagingResponse()
    r.message(f"Thanks for the SMS message, {user.first_name}!")
    return r


def get_dashboard_stats(hours_tracked):
    total_hours_sum = hours_tracked.aggregate(total_hours=Sum("hours"))["total_hours"]
    total_amount_sum = hours_tracked.annotate(
        total_amount=F("hours") * F("invoice__hourly_rate")
    ).aggregate(total=Sum("total_amount"))["total"]

    stats = {
        "total_hours": total_hours_sum or 0,
        "total_amount": total_amount_sum or 0,
    }
    return stats


def get_hours_tracked(user):
    current_month = DailyHoursInput.all_hours.current_month(user)
    last_month = DailyHoursInput.all_hours.last_month(user)
    current_year = DailyHoursInput.all_hours.current_year(user)
    context = {
        "current_month": get_dashboard_stats(current_month),
        "last_month": get_dashboard_stats(last_month),
        "current_year": get_dashboard_stats(current_year),
    }
    return context


@login_required
@require_http_methods(["GET"])
def index(request):
    user = request.user
    context = {
        "new_hours": DailyHoursForm(user=user),
        "hours": DailyHoursInput.all_hours.current_month(user),
    }
    context.update(get_hours_tracked(user))
    return render(request, "timary/index.html", context=context)


@login_required()
@require_http_methods(["GET"])
def dashboard_stats(request):
    return render(
        request,
        "partials/_dashboard_stats.html",
        get_hours_tracked(request.user),
    )
