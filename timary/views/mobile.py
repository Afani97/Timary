from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    parser_classes,
    permission_classes,
    renderer_classes,
)
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework_xml.renderers import XMLRenderer

from timary.forms import DailyHoursForm, UserForm
from timary.models import DailyHoursInput
from timary.utils import render_xml
from timary.views import get_hours_tracked


def mobile_index(request):
    return render_xml(request, "index.xml")


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def mobile_hours(request):
    hours = DailyHoursInput.all_hours.current_month(request.user)
    show_repeat_option = request.user.can_repeat_previous_hours_logged(hours)

    context = {
        "new_hour_form": DailyHoursForm(user=request.user),
        "hours": hours,
        "show_repeat": show_repeat_option,
    }
    context.update(get_hours_tracked(request.user))
    if "partial" in request.query_params:
        return render_xml(request, "hours/_hours.xml", context)
    else:
        return render_xml(request, "hours/hours.xml", context)


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@renderer_classes([XMLRenderer])
@parser_classes([FormParser, MultiPartParser])
def mobile_new_hours(request):
    if request.method == "POST":
        hours = DailyHoursForm(request.data)
        if hours.is_valid():
            hours.save()
            return render_xml(
                request, "new-hours/new_hours_form.xml", {"success": True}
            )
        else:
            return render_xml(
                request, "new-hours/new_hours_form.xml", {"errors": hours.errors}
            )
    else:
        return render_xml(
            request,
            "new-hours/new_hours.xml",
            {"user_invoices": request.user.get_invoices},
        )


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def mobile_view_hours(request, hours_id):
    hour = get_object_or_404(DailyHoursInput, id=hours_id)
    if request.user != hour.invoice.user:
        raise Http404
    return render_xml(request, "hours/_hour.xml", {"hour": hour})


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def mobile_hour_stats(request):
    return render_xml(request, "hours/_stats.xml", get_hours_tracked(request.user))


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@renderer_classes([XMLRenderer])
@parser_classes([FormParser, MultiPartParser])
def mobile_edit_hours(request, hours_id):
    hour = get_object_or_404(DailyHoursInput, id=hours_id)
    if request.user != hour.invoice.user:
        raise Http404
    if request.method == "POST":
        hours = DailyHoursForm(request.data, instance=hour)
        if hours.is_valid():
            hours.save()
            context = {"hour": hour, "success": True}
        else:
            context = {"hour": hour, "errors": hours.errors}
        return render_xml(request, "edit-hours/edit_hours_form.xml", context)
    else:
        return render_xml(
            request,
            "edit-hours/edit_hours.xml",
            {"hour": hour, "user_invoices": request.user.get_invoices},
        )


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def mobile_delete_hours(request, hours_id):
    hours = get_object_or_404(DailyHoursInput, id=hours_id)
    if request.user != hours.invoice.user:
        raise Http404
    hours.delete()
    return render_xml(request, "empty.xml")


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def mobile_profile(request):
    t = "profile/profile.xml"
    if "partial" in request.query_params:
        t = "profile/_profile.xml"
    return render_xml(request, t, {"profile": request.user})


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@renderer_classes([XMLRenderer])
@parser_classes([FormParser, MultiPartParser])
def mobile_edit_profile(request):
    if request.method == "POST":
        profile = UserForm(request.data, instance=request.user)
        if profile.is_valid():
            profile.save()
            context = {"profile": request.user, "success": True}
        else:
            context = {"profile": request.user, "errors": profile.errors}
        return render_xml(request, "edit-profile/edit_profile_form.xml", context)
    else:
        return render_xml(
            request, "edit-profile/edit_profile.xml", {"profile": request.user}
        )
