from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_http_methods


@login_required()
@require_http_methods(["GET"])
def user_profile(request):
    userprofile = request.user.userprofile
    return render(request, "timary/profile.html", {"profile": userprofile})
