from django.shortcuts import render


def mobile_index(request):
    return render(request, "mobile/index.xml", content_type="application/xml")
