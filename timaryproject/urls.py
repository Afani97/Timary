"""timaryproject URL Configuration
"""
from django.contrib import admin
from django.urls import include, path

from timary import views

handler404 = views.bad_request

urlpatterns = [
    path("", include("timary.urls")),
    path("admin/", admin.site.urls),
]
