from django.shortcuts import render
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import IsAuthenticated


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
    return render(request, "mobile/profile.xml", content_type="application/xml")
