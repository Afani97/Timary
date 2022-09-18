from django.http import Http404
from django.shortcuts import render, get_object_or_404
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    renderer_classes,
    parser_classes,
)
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_xml.renderers import XMLRenderer

from timary.forms import UserForm, DailyHoursForm
from timary.models import DailyHoursInput
from timary.views import get_hours_tracked


def mobile_index(request):
    return render(request, "mobile/index.xml", content_type="application/xml")


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
        return render(
            request,
            "mobile/hours/_hours.xml",
            context=context,
            content_type="application/xml",
        )
    return render(
        request,
        "mobile/hours/hours.xml",
        context=context,
        content_type="application/xml",
    )


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def mobile_hour_stats(request):
    context = {}
    context.update(get_hours_tracked(request.user))
    return render(
        request,
        "mobile/hours/_stats.xml",
        context=context,
        content_type="application/xml",
    )


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def mobile_edit_hours(request, hours_id):
    hours = DailyHoursInput.all_hours.current_month(request.user)
    show_repeat_option = request.user.can_repeat_previous_hours_logged(hours)

    context = {
        "new_hour_form": DailyHoursForm(user=request.user),
        "hours": hours,
        "show_repeat": show_repeat_option,
    }
    context.update(get_hours_tracked(request.user))
    return render(
        request,
        "mobile/hours/hours.xml",
        context=context,
        content_type="application/xml",
    )


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def mobile_delete_hours(request, hours_id):
    hours = get_object_or_404(DailyHoursInput, id=hours_id)
    if request.user != hours.invoice.user:
        raise Http404
    hours.delete()
    return render(
        request,
        "mobile/empty.xml",
        content_type="application/xml",
    )


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def mobile_profile(request):
    if "partial" in request.query_params:
        return render(
            request,
            "mobile/profile/_profile.xml",
            {"profile": request.user},
            content_type="application/xml",
        )
    return render(
        request,
        "mobile/profile/profile.xml",
        {"profile": request.user},
        content_type="application/xml",
    )


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
            return render(
                request,
                "mobile/edit-profile/edit_profile_form.xml",
                {"profile": request.user, "success": True},
                content_type="application/xml",
            )
        else:
            return render(
                request,
                "mobile/edit-profile/edit_profile_form.xml",
                {"profile": request.user, "errors": profile.errors},
                content_type="application/xml",
            )
    else:
        return render(
            request,
            "mobile/edit-profile/edit_profile.xml",
            {"profile": request.user},
            content_type="application/xml",
        )
