import datetime
import json

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404, HttpResponse, QueryDict
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from timary.forms import DailyHoursForm
from timary.hours_manager import HoursManager
from timary.models import DailyHoursInput, Invoice
from timary.tasks import gather_recurring_hours
from timary.utils import show_alert_message


@login_required()
@require_http_methods(["POST"])
def create_daily_hours(request):
    hours_form = DailyHoursForm(request.POST, user=request.user)
    if hours_form.is_valid():
        hours_saved = hours_form.save()
        if "recurring_logic" in hours_form.cleaned_data:
            hours_saved.recurring_logic = hours_form.cleaned_data.get("recurring_logic")
            hours_saved.save()
        hours_manager = HoursManager(request.user)
        show_repeat_option = hours_manager.can_repeat_previous_hours_logged()
        show_most_frequent_options = hours_manager.show_most_frequent_options()

        context = {
            "hours": hours_manager.hours,
            "show_repeat": show_repeat_option,
        }
        if len(show_most_frequent_options) > 0:
            context["frequent_options"] = show_most_frequent_options
        response = render(request, "partials/_hours_list.html", context=context)
        response[
            "HX-Trigger-After-Swap"
        ] = "clearHoursModal"  # To trigger modal closing
        # "newHours" - To trigger dashboard stats refresh
        show_alert_message(response, "success", "New hours added!", "newHours")
        return response
    else:
        response = render(request, "hours/_create.html", {"form": hours_form})
        response["HX-Retarget"] = "#new-hours-form"
        return response


@login_required()
@require_http_methods(["GET"])
def quick_hours(request):
    try:
        hours, invoice_id = request.GET.get("hours_ref_id").split("_")
    except Exception:
        response = HttpResponse(status=204)
        show_alert_message(response, "warning", "Error adding hours")
        return response
    hours_form = DailyHoursForm(
        data={
            "hours": hours,
            "date_tracked": datetime.date.today(),
            "invoice": Invoice.objects.get(email_id=invoice_id),
        },
        user=request.user,
    )
    if hours_form.is_valid():
        hours_form.save()
        hours_manager = HoursManager(request.user)
        show_most_frequent_options = hours_manager.show_most_frequent_options()
        context = {
            "hours": hours_manager.hours,
        }
        if len(show_most_frequent_options) > 0:
            context["frequent_options"] = show_most_frequent_options
        response = render(request, "partials/_hours_list.html", context=context)
        # "newHours" - To trigger dashboard stats refresh
        show_alert_message(response, "success", "New hours added!", "newHours")
        return response
    else:
        response = HttpResponse(status=204)
        show_alert_message(response, "warning", "Unable to add hours")
        return response


@login_required()
@require_http_methods(["GET"])
def get_hours(request, hours_id):
    hours = get_object_or_404(DailyHoursInput, id=hours_id)
    if request.user != hours.invoice.user:
        raise Http404
    return render(request, "partials/_hour.html", {"hour": hours})


@login_required()
@require_http_methods(["GET"])
def edit_hours(request, hours_id):
    hours = get_object_or_404(DailyHoursInput, id=hours_id)
    if request.user != hours.invoice.user:
        raise Http404
    hours_form = DailyHoursForm(instance=hours, user=request.user)
    return render(request, "hours/_update.html", {"hour": hours, "form": hours_form})


@login_required()
@require_http_methods(["PUT"])
def update_hours(request, hours_id):
    hours = get_object_or_404(DailyHoursInput, id=hours_id)
    if request.user != hours.invoice.user:
        raise Http404
    put_params = QueryDict(request.body)
    hours_form = DailyHoursForm(put_params, instance=hours, user=request.user)
    if hours_form.is_valid():
        updated_hours = hours_form.save()
        if "recurring_logic" in hours_form.cleaned_data:
            updated_hours.recurring_logic = hours_form.cleaned_data.get(
                "recurring_logic"
            )
            updated_hours.save()
        response = render(request, "partials/_hour.html", {"hour": updated_hours})
        # "newHours" - To trigger dashboard stats refresh
        show_alert_message(response, "success", "Hours updated", "newHours")
        return response
    else:
        return render(
            request, "hours/_update.html", {"hour": hours, "form": hours_form}
        )


@login_required()
@require_http_methods(["PATCH"])
def patch_hours(request, hours_id):
    hour = get_object_or_404(DailyHoursInput, id=hours_id)
    if request.user != hour.invoice.user:
        raise Http404
    put_params = QueryDict(request.body)
    hours_form = DailyHoursForm(put_params, instance=hour, user=request.user)
    if hours_form.is_valid():
        hour.hours = hours_form.cleaned_data.get("hours")
        hour.date_tracked = hours_form.cleaned_data.get("date_tracked")
        hour.save()
        response = render(
            request,
            "hours/_patch.html",
            {"form": hours_form, "success_msg": "Successfully updated hours!"},
        )
        response[
            "HX-Trigger"
        ] = f"refreshHourStats-{hour.invoice.email_id}"  # To trigger hours stats refresh
        return response
    else:
        return render(request, "hours/_patch.html", {"form": hours_form})


@login_required()
@require_http_methods(["DELETE"])
def delete_hours(request, hours_id):
    hours = get_object_or_404(DailyHoursInput, id=hours_id)
    if request.user != hours.invoice.user:
        raise Http404
    hours.delete()
    response = HttpResponse("", status=200)
    response["HX-Trigger"] = json.dumps(
        {"newHours": None, f"refreshHourStats-{hours.invoice.email_id}": None}
    )  # To trigger stats refresh
    return response


@login_required()
@require_http_methods(["GET"])
def repeat_hours(request):
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    yesterday_hours = DailyHoursInput.objects.filter(
        invoice__user=request.user,
        date_tracked=yesterday,
        invoice__is_archived=False,
        hours__gt=0,
    ).filter(Q(recurring_logic__exact={}) | Q(recurring_logic__isnull=True))
    hours = []
    for hour in yesterday_hours:
        hours.append(
            DailyHoursInput.objects.create(
                date_tracked=datetime.date.today(),
                hours=hour.hours,
                invoice=hour.invoice,
            )
        )

    # Add recurring hours if scheduled for today or daily
    gather_recurring_hours()

    hours_manager = HoursManager(request.user)
    show_most_frequent_options = hours_manager.show_most_frequent_options()
    context = {
        "hours": hours_manager.hours,
    }
    if len(show_most_frequent_options) > 0:
        context["frequent_options"] = show_most_frequent_options
    response = render(request, "partials/_hours_list.html", context)
    # "newHours" - To trigger dashboard stats refresh
    show_alert_message(
        response, "success", "Yesterday's hours repeated again today", "newHours"
    )
    return response


@login_required()
@require_http_methods(["GET"])
def update_timer(request):
    timer_val = request.GET.get("timerVal", None)
    timer_paused = request.GET.get("timerPaused", None)
    timer_stopped = request.GET.get("timerStopped", None)
    if timer_stopped and timer_stopped == "true":
        request.user.timer_is_active = None
        request.user.save()
        return HttpResponse("Stopped")
    request.user.timer_is_active = f"{timer_val},{timer_paused}"
    request.user.save()
    return HttpResponse("Ok")
