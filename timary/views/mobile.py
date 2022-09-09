from django.shortcuts import render


def mobile_index(request):
    return render(request, "mobile/index.xml", content_type="application/xml")


def mobile_home(request):
    return render(request, "mobile/home.xml", content_type="application/xml")


def mobile_profile(request):
    return render(request, "mobile/profile.xml", content_type="application/xml")
