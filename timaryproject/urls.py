"""timaryproject URL Configuration
"""
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from timary import views

handler404 = views.bad_request

urlpatterns = [
    path("", include("timary.urls")),
    path("admin/", admin.site.urls),
    # auth password reset
    path(
        "password_reset/",
        auth_views.PasswordResetView.as_view(
            template_name="timary/registration/password_reset_form.html"
        ),
        name="password_reset",
    ),
    path(
        "password_reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="timary/registration/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="timary/registration/password_reset_confirm.html"
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="timary/registration/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
    path("__reload__/", include("django_browser_reload.urls")),
]
