import json

from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def start_timer(request):
    request.user.timer_is_active = "20000,true"
    request.user.save()
    response = render(request, "partials/_timer.html", {"timer_running": True})
    response["HX-Trigger"] = json.dumps(
        {
            "updateTimer": {
                "active_timer_ms": 20000,
                "action": "start",
            },
        }
    )
    return response


@login_required
def pause_timer(request):
    request.user.timer_is_active = "20000,false"
    request.user.save()
    response = render(request, "partials/_timer.html", {"timer_running": False})
    response["HX-Trigger"] = json.dumps(
        {
            "updateTimer": {
                "active_timer_ms": 15000,
                "action": "pause",
            },
        }
    )
    return response


@login_required
def stop_timer(request):
    request.user.timer_is_active = "20000,false"
    request.user.save()
    response = render(request, "partials/_timer.html", {"timer_running": False})
    response["HX-Trigger"] = json.dumps(
        {
            "updateTimer": {
                "active_timer_ms": 20000,
                "action": "stop",
            },
        }
    )
    return response


@login_required
def resume_timer(request):
    request.user.timer_is_active = "25000,true"
    request.user.save()
    response = render(request, "partials/_timer.html", {"timer_running": True})
    response["HX-Trigger"] = json.dumps(
        {
            "updateTimer": {
                "active_timer_ms": 25000,
                "action": "resume",
            },
        }
    )
    return response


@login_required
def reset_timer(request):
    request.user.timer_is_active = "0,false"
    request.user.save()
    response = render(request, "partials/_timer.html", {"timer_running": True})
    response["HX-Trigger"] = json.dumps(
        {
            "updateTimer": {
                "active_timer_ms": 0,
                "action": "reset",
            },
        }
    )
    return response
