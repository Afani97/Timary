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
    path("terms/", views.terms_page, name="terms"),
    path("privacy/", views.privacy_page, name="privacy"),
    path("close_account/", views.close_account, name="close_account"),
    path(
        "confirm_close_account/",
        views.confirm_close_account,
        name="confirm_close_account",
    ),
    path("questions/", views.questions, name="questions"),
    path("contract/", views.contract_builder, name="contract_builder"),
]


# PROFILE URLS
urlpatterns += [
    path("profile/", views.user_profile, name="user_profile"),
    path("profile/partial/", views.profile_partial, name="user_profile_partial"),
    path("profile/update/", views.update_user_profile, name="update_user_profile"),
    path("profile/edit/", views.edit_user_profile, name="edit_user_profile"),
]

# SETTINGS URLS
urlpatterns += [
    path(
        "profile/settings/sms/",
        views.update_sms_settings,
        name="update_sms_settings",
    ),
    path(
        "profile/settings/membership/",
        views.update_membership_settings,
        name="update_membership_settings",
    ),
    path(
        "profile/settings/payment-method/",
        views.update_payment_method_settings,
        name="update_payment_method_settings",
    ),
    path(
        "profile/settings/accounting/",
        views.update_accounting_integrations,
        name="update_accounting_integrations",
    ),
    path(
        "profile/settings_partial/<str:setting>/",
        views.settings_partial,
        name="settings_partial",
    ),
    path(
        "profile/invoice_branding/",
        views.update_invoice_branding,
        name="update_invoice_branding",
    ),
    path("audit/", views.audit, name="audit"),
    path("invite/", views.invite_new_user, name="invite_new_user"),
]


# HOURS URLS
urlpatterns += [
    path("hours/", views.create_daily_hours, name="create_hours"),
    path("hours/repeat/", views.repeat_hours, name="repeat_hours"),
    path("hours/<uuid:hours_id>/", views.get_hours, name="get_single_hours"),
    path("hours/<uuid:hours_id>/edit/", views.edit_hours, name="edit_hours"),
    path("hours/<uuid:hours_id>/update/", views.update_hours, name="update_hours"),
    path("hours/<uuid:hours_id>/patch/", views.patch_hours, name="patch_hours"),
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
        "invoices/<uuid:invoice_id>/archive/",
        views.archive_invoice,
        name="archive_invoice",
    ),
    path(
        "invoices/<uuid:invoice_id>/update/",
        views.update_invoice,
        name="update_invoice",
    ),
    path(
        "invoices/<uuid:sent_invoice_id>/remind/",
        views.resend_invoice_email,
        name="resend_invoice_email",
    ),
    path(
        "invoices/<uuid:invoice_id>/generate/",
        views.generate_invoice,
        name="generate_invoice",
    ),
    path(
        "invoices/<uuid:invoice_id>/edit_invoice_hours/",
        views.edit_invoice_hours,
        name="edit_invoice_hours",
    ),
    path(
        "invoices/<uuid:invoice_id>/invoice_hour_stats/",
        views.invoice_hour_stats,
        name="invoice_hour_stats",
    ),
    path(
        "invoices/<uuid:invoice_id>/sent_invoices/",
        views.sent_invoices_list,
        name="sent_invoices_list",
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
    path("accounting-connect/", views.accounting_connect, name="accounting_connect"),
    path(
        "accounting-disconnect/",
        views.accounting_disconnect,
        name="accounting_disconnect",
    ),
    path("accounting-redirect/", views.accounting_redirect, name="accounting_redirect"),
]


# STRIPE URLS
urlpatterns += [
    path("stripe-webhook/", views.stripe_webhook, name="stripe_webhook"),
    path(
        "invoice-payment/<uuid:sent_invoice_id>/", views.pay_invoice, name="pay_invoice"
    ),
    path(
        "invoice-payment/<uuid:sent_invoice_id>/quick-pay/",
        views.quick_pay_invoice,
        name="quick_pay_invoice",
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

urlpatterns += [
    path("mobile/index/", views.mobile_index, name="mobile_index"),
    path(
        "mobile/hours/<uuid:hours_id>/",
        views.mobile_view_hours,
        name="mobile_view_hours",
    ),
    path(
        "mobile/hours/<uuid:hours_id>/edit/",
        views.mobile_edit_hours,
        name="mobile_edit_hours",
    ),
    path(
        "mobile/hours/<uuid:hours_id>/delete/",
        views.mobile_delete_hours,
        name="mobile_delete_hours",
    ),
    path("mobile/hours/", views.mobile_hours, name="mobile_hours"),
    path("mobile/hours/new/", views.mobile_new_hours, name="mobile_new_hours"),
    path("mobile/hours/stats/", views.mobile_hour_stats, name="mobile_hour_stats"),
    path("mobile/invoices/", views.mobile_invoices, name="mobile_invoices"),
    path("mobile/invoices/new/", views.mobile_new_invoices, name="mobile_new_invoices"),
    path("mobile/profile/", views.mobile_profile, name="mobile_profile"),
    path("mobile/profile/edit/", views.mobile_edit_profile, name="mobile_edit_profile"),
    path("api-token-auth/", views.CustomAuthToken.as_view(), name="obtain_auth_token"),
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
