import datetime
import json

from crispy_forms.utils import render_crispy_form
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, QueryDict
from django.shortcuts import get_object_or_404, render
from django.template.context_processors import csrf
from django.views.decorators.http import require_http_methods

from timary.forms import DailyHoursForm
from timary.models import DailyHoursInput
from timary.utils import render_form_errors, render_form_messages, show_alert_message


@login_required()
@require_http_methods(["POST"])
def create_daily_hours(request):
    hours_form = DailyHoursForm(
        request.POST,
        user=request.user,
        is_mobile=request.is_mobile,
        request_method="get",
    )
    if hours_form.is_valid():
        hours_form.save()
        hours = DailyHoursInput.all_hours.current_month(request.user)
        show_repeat_option = request.user.can_repeat_previous_hours_logged(hours)

        context = {
            "hours": hours,
            "show_repeat": show_repeat_option,
        }
        response = render(request, "partials/_hours_list.html", context=context)
        response["HX-Trigger-After-Swap"] = "clearModal"  # To trigger modal closing
        # "newHours" - To trigger dashboard stats refresh
        show_alert_message(response, "success", "New hours added!", "newHours")
        return response
    ctx = {}
    ctx.update(csrf(request))
    hours_form.helper.layout.insert(0, render_form_errors(hours_form))
    html_form = render_crispy_form(hours_form, context=ctx)
    # Wrap html form in .inner-modal to replace and keep div in place inside modal, otherwise errors will override
    # html form and remove it.
    html_form = f"""
    <div class="inner-modal">
        {html_form}
    </div>
    """
    response = HttpResponse(html_form)
    response["HX-Retarget"] = ".inner-modal"
    # Trigger removing first modal form until they enable a 'HX-Reswap'
    response["HX-RemoveInitialHourModal"] = "resetNewHourModal"
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
    hours_form = DailyHoursForm(
        instance=hours,
        user=request.user,
        is_mobile=request.is_mobile,
        request_method="put",
    )
    ctx = {}
    ctx.update(csrf(request))
    hours_form.helper.layout.insert(0, render_form_errors(hours_form))
    html_form = render_crispy_form(hours_form, context=ctx)
    return HttpResponse(html_form)


@login_required()
@require_http_methods(["PUT"])
def update_hours(request, hours_id):
    hours = get_object_or_404(DailyHoursInput, id=hours_id)
    if request.user != hours.invoice.user:
        raise Http404
    put_params = QueryDict(request.body)
    hours_form = DailyHoursForm(
        put_params,
        instance=hours,
        user=request.user,
        is_mobile=request.is_mobile,
        request_method="put",
    )
    if hours_form.is_valid():
        updated_hours = hours_form.save()
        response = render(request, "partials/_hour.html", {"hour": updated_hours})
        # "newHours" - To trigger dashboard stats refresh
        show_alert_message(response, "success", "Hours updated", "newHours")
        return response
    ctx = {}
    ctx.update(csrf(request))
    hours_form.helper.layout.insert(0, render_form_errors(hours_form))
    html_form = render_crispy_form(hours_form, context=ctx)
    return HttpResponse(html_form, status=200)


@login_required()
@require_http_methods(["PATCH"])
def patch_hours(request, hours_id):
    hour = get_object_or_404(DailyHoursInput, id=hours_id)
    if request.user != hour.invoice.user:
        raise Http404
    put_params = QueryDict(request.body)
    hours_form = DailyHoursForm(
        put_params,
        instance=hour,
        user=request.user,
        is_mobile=request.is_mobile,
        request_method="patch",
        invoice_id=hour.invoice.id,
    )
    if hours_form.is_valid():
        hour.hours = hours_form.cleaned_data.get("hours")
        hour.date_tracked = hours_form.cleaned_data.get("date_tracked")
        hour.save()
        ctx = {}
        ctx.update(csrf(request))
        hours_form.helper.layout.insert(
            0, render_form_messages(["Successfully updated hours"])
        )
        html_form = render_crispy_form(hours_form, context=ctx)
        response = HttpResponse(html_form)
        response["HX-Trigger"] = "refreshHourStats"  # To trigger hours stats refresh
        return response
    ctx = {}
    ctx.update(csrf(request))
    hours_form.helper.layout.insert(0, render_form_errors(hours_form))
    html_form = render_crispy_form(hours_form, context=ctx)
    return HttpResponse(html_form, status=200)


@login_required()
@require_http_methods(["DELETE"])
def delete_hours(request, hours_id):
    hours = get_object_or_404(DailyHoursInput, id=hours_id)
    if request.user != hours.invoice.user:
        raise Http404
    hours.delete()
    response = HttpResponse("", status=200)
    response["HX-Trigger"] = json.dumps(
        {"newHours": None, "refreshHourStats": None}
    )  # To trigger stats refresh
    return response


@login_required()
@require_http_methods(["GET"])
def repeat_hours(request):
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    yesterday_hours = DailyHoursInput.objects.filter(
        invoice__user=request.user, date_tracked=yesterday
    )
    hours = []
    for hour in yesterday_hours:
        hours.append(
            DailyHoursInput.objects.create(
                date_tracked=datetime.date.today(),
                hours=hour.hours,
                invoice=hour.invoice,
            )
        )

    response = render(request, "partials/_hours_grid.html", {"hours": hours})
    # "newHours" - To trigger dashboard stats refresh
    show_alert_message(
        response, "success", "Yesterday's hours repeated again today", "newHours"
    )
    return response
