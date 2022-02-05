from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path

from timary import views
from timary.admin import TimaryAdminSite

app_name = "timary"

admin.site.__class__ = TimaryAdminSite

urlpatterns = [
    path("", views.landing_page, name="landing_page"),
    path("main/", views.index, name="index"),
    path("dashboard_stats/", views.dashboard_stats, name="dashboard_stats"),
    path("twilio-reply/", views.twilio_reply, name="twilio_reply"),
]


# PROFILE URLS
urlpatterns += [
    path("profile/", views.user_profile, name="user_profile"),
    path("profile/partial/", views.profile_partial, name="user_profile_partial"),
    path("profile/update/", views.update_user_profile, name="update_user_profile"),
    path("profile/edit/", views.edit_user_profile, name="edit_user_profile"),
    path(
        "profile/settings/",
        views.update_user_settings,
        name="update_user_settings",
    ),
    path(
        "profile/settings/partial/",
        views.settings_partial,
        name="settings_partial",
    ),
]


# HOURS URLS
urlpatterns += [
    path("hours/", views.create_daily_hours, name="create_hours"),
    path("hours/<uuid:hours_id>/", views.get_hours, name="get_single_hours"),
    path("hours/<uuid:hours_id>/edit/", views.edit_hours, name="edit_hours"),
    path("hours/<uuid:hours_id>/update/", views.update_hours, name="update_hours"),
    path("hours/<uuid:hours_id>/delete/", views.delete_hours, name="delete_hours"),
]


# INVOICE URLS
urlpatterns += [
    path("invoices/", views.create_invoice, name="create_invoice"),
    path("invoices/manage/", views.manage_invoices, name="manage_invoices"),
    path("invoices/<uuid:invoice_id>/", views.get_invoice, name="get_single_invoice"),
    path("invoices/<uuid:invoice_id>/edit/", views.edit_invoice, name="edit_invoice"),
    path(
        "invoices/<uuid:invoice_id>/pause/", views.pause_invoice, name="pause_invoice"
    ),
    path(
        "invoices/<uuid:invoice_id>/update/",
        views.update_invoice,
        name="update_invoice",
    ),
    path(
        "invoices/<uuid:invoice_id>/delete/",
        views.delete_invoice,
        name="delete_invoice",
    ),
    path(
        "invoices/<uuid:sent_invoice_id>/remind/",
        views.resend_invoice_email,
        name="resend_invoice_email",
    ),
    path("invoices/new_btn/", views.create_invoice_partial, name="create_invoice_btn"),
]

# AUTH URLS
urlpatterns += [
    path("login/", views.login_user, name="login"),
    path("logout/", views.logout_user, name="logout"),
    path("register/", views.register_user, name="register"),
]

# ACCOUNTING INTEGRATION URLS
urlpatterns += [
    path("quickbooks-connect/", views.quickbooks_connect, name="quickbooks_connect"),
    path("quickbooks-redirect/", views.quickbooks_redirect, name="quickbooks_redirect"),
]


# STRIPE URLS
urlpatterns += [
    path(
        "invoice-payment/<uuid:sent_invoice_id>/", views.pay_invoice, name="pay_invoice"
    ),
    path(
        "invoice-payment-success/<uuid:sent_invoice_id>/",
        views.invoice_payment_success,
        name="invoice_payment_success",
    ),
    path(
        "onboarding_success/",
        views.onboard_success,
        name="onboard_success",
    ),
    path(
        "update_connect/",
        views.update_connect_account,
        name="update_connect",
    ),
    path(
        "complete_connect/",
        views.completed_connect_account,
        name="complete_connect",
    ),
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
