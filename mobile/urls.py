from django.urls import path

from mobile import views

app_name = "mobile"

urlpatterns = [
    path("index/", views.index, name="index"),
    path("api-token-auth/", views.CustomAuthToken.as_view(), name="obtain_auth_token"),
]

# HOURS
urlpatterns += [
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
    path("hours/", views.get_hours, name="hours"),
    path("hours/new/", views.new_hours, name="new_hours"),
    path("hours/stats/", views.hour_stats, name="hour_stats"),
]

# INVOICES
urlpatterns += [
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
    path("invoices/", views.get_invoices, name="invoices"),
    path("invoices/new/", views.new_invoices, name="new_invoices"),
]


# SENT INVOICES
urlpatterns += [
    path(
        "sent_invoices/<uuid:sent_invoice_id>/",
        views.view_sent_invoice,
        name="view_sent_invoice",
    ),
    path(
        "sent_invoices/<uuid:sent_invoice_id>/resend/",
        views.resend_invoice,
        name="resend_invoice",
    ),
    path("sent_invoices/", views.get_sent_invoices, name="sent_invoices"),
]


# PROFILE
urlpatterns += [
    path("profile/", views.get_profile, name="profile"),
    path("profile/edit/", views.edit_profile, name="edit_profile"),
]


# APP INFO
urlpatterns += [
    path("terms/", views.get_terms_page, name="terms_page"),
    path("privacy/", views.get_privacy_page, name="privacy_page"),
]
