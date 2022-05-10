import datetime

from crispy_forms.utils import render_crispy_form
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, QueryDict
from django.shortcuts import get_object_or_404, render
from django.template.context_processors import csrf
from django.views.decorators.http import require_http_methods

from timary.forms import DailyHoursForm
from timary.models import DailyHoursInput
from timary.utils import render_form_errors


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
        latest_date_tracked = (
            hours.order_by("-date_tracked").first().date_tracked
            if hours.order_by("-date_tracked").first()
            else None
        )
        show_repeat = False
        if latest_date_tracked != datetime.date.today():
            show_repeat = True

        context = {
            "hours": hours,
            "show_repeat": show_repeat,
        }
        response = render(request, "partials/_invoice_list.html", context=context)
        response["HX-Trigger"] = "newHours"  # To trigger dashboard stats refresh
        response["HX-Trigger-After-Swap"] = "clearModal"  # To trigger modal closing
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
        response["HX-Trigger"] = "newHours"  # To trigger dashboard stats refresh
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
    response["HX-Trigger"] = "newHours"  # To trigger dashboard stats refresh
    return response
