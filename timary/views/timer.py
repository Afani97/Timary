import datetime
import json

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from timary.utils import calculate_accumulative_time


@login_required
def start_timer(request):
    timer = {
        "running_times": [],
        "timer_running": True,
        "time_started": datetime.datetime.timestamp(datetime.datetime.now()),
    }
    request.user.timer_is_active = timer
    request.user.save()
    response = render(request, "partials/_timer.html", {"timer_running": True})
    response["HX-Trigger"] = json.dumps(
        {
            "updateTimer": {
                "active_timer_ms": 0,
                "action": "start",
            },
        }
    )
    return response


@login_required
def pause_timer(request):
    user_timer = request.user.timer_is_active
    current_running_times = list(user_timer["running_times"])
    now = datetime.datetime.timestamp(datetime.datetime.now())
    current_running_times.append(now - int(user_timer["time_started"]))
    timer = {
        "running_times": current_running_times,
        "timer_running": False,
    }
    request.user.timer_is_active = timer
    request.user.save()
    response = render(request, "partials/_timer.html", {"timer_running": False})
    response["HX-Trigger"] = json.dumps(
        {
            "updateTimer": {
                "active_timer_ms": calculate_accumulative_time(timer["running_times"]),
                "action": "pause",
            },
        }
    )
    return response


@login_required
def stop_timer(request):
    user_timer = request.user.timer_is_active
    current_running_times = list(user_timer["running_times"])
    if "time_started" in user_timer:
        now = datetime.datetime.timestamp(datetime.datetime.now())
        current_running_times.append(now - int(user_timer["time_started"]))
    total_time = calculate_accumulative_time(current_running_times)
    timer = {
        "running_times": [],
        "timer_running": False,
    }
    request.user.timer_is_active = timer
    request.user.save()
    response = render(request, "partials/_timer.html", {"timer_running": False})
    response["HX-Trigger"] = json.dumps(
        {
            "updateTimer": {
                "active_timer_ms": total_time,
                "action": "stop",
            },
        }
    )
    return response


@login_required
def resume_timer(request):
    user_timer = request.user.timer_is_active
    timer = {
        "running_times": user_timer["running_times"],
        "timer_running": True,
        "time_started": datetime.datetime.timestamp(datetime.datetime.now()),
    }
    request.user.timer_is_active = timer
    request.user.save()
    response = render(request, "partials/_timer.html", {"timer_running": True})
    response["HX-Trigger"] = json.dumps(
        {
            "updateTimer": {
                "active_timer_ms": calculate_accumulative_time(timer["running_times"]),
                "action": "resume",
            },
        }
    )
    return response


@login_required
def reset_timer(request):
    timer = {
        "running_times": [],
        "timer_running": True,
        "time_started": datetime.datetime.timestamp(datetime.datetime.now()),
    }
    request.user.timer_is_active = timer
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
