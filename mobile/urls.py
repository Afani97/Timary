from django.urls import path

from mobile import views

app_name = "mobile"

urlpatterns = [
    path("index/", views.index, name="index"),
    path(
        "hours/<uuid:hours_id>/",
        views.view_hours,
        name="view_hours",
    ),
    path(
        "hours/<uuid:hours_id>/edit/",
        views.edit_hours,
        name="edit_hours",
    ),
    path(
        "hours/<uuid:hours_id>/delete/",
        views.delete_hours,
        name="delete_hours",
    ),
    path("hours/", views.hours, name="hours"),
    path("hours/new/", views.new_hours, name="new_hours"),
    path("hours/stats/", views.hour_stats, name="hour_stats"),
    path(
        "invoices/<uuid:invoice_id>/",
        views.view_invoice,
        name="view_invoice",
    ),
    path(
        "invoices/<uuid:invoice_id>/edit/",
        views.edit_invoice,
        name="edit_invoice",
    ),
    path("invoices/", views.invoices, name="invoices"),
    path("invoices/new/", views.new_invoices, name="new_invoices"),
    path("profile/", views.profile, name="profile"),
    path("profile/edit/", views.edit_profile, name="edit_profile"),
    path("api-token-auth/", views.CustomAuthToken.as_view(), name="obtain_auth_token"),
]
