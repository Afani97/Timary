from django.shortcuts import render
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
from rest_framework_xml.renderers import XMLRenderer

from timary.forms import UserForm


def mobile_index(request):
    return render(request, "mobile/index.xml", content_type="application/xml")


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def mobile_home(request):
    return render(request, "mobile/home.xml", content_type="application/xml")


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
