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
    path("main/calendar", views.hours_calendar, name="calendar"),
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
    path("stopwatch/", views.stopwatch, name="stopwatch"),
    path("invoice/", views.invoice_generator, name="invoice_generator"),
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
        "profile/settings/subscription/",
        views.update_subscription,
        name="update_subscription",
    ),
    path(
        "profile/settings/password/",
        views.update_user_password,
        name="update_user_password",
    ),
    path("profile/settings/tax_center/", views.view_tax_center, name="view_tax_center"),
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
    path("tax_center/summary/", views.download_tax_summary_pdf, name="tax_summary_pdf"),
    path("invite/", views.invite_new_user, name="invite_new_user"),
]


# HOURS URLS
urlpatterns += [
    path("hours/", views.create_daily_hours, name="create_hours"),
    path("hours/quick/", views.quick_hours, name="quick_hours"),
    path("hours/repeat/", views.repeat_hours, name="repeat_hours"),
    path("hours/month/", views.hours_for_month, name="hours_for_month"),
    path("hours/<uuid:hours_id>/", views.get_hours, name="get_single_hours"),
    path("hours/<uuid:hours_id>/edit/", views.edit_hours, name="edit_hours"),
    path("hours/<uuid:hours_id>/update/", views.update_hours, name="update_hours"),
    path("hours/<uuid:hours_id>/patch/", views.patch_hours, name="patch_hours"),
    path("hours/<uuid:hours_id>/delete/", views.delete_hours, name="delete_hours"),
    path(
        "hours/<uuid:hours_id>/cancel",
        views.cancel_recurring_hour,
        name="cancel_recurring_hour",
    ),
]

# EXPENSE URLS
urlpatterns += [
    path("expenses/<uuid:invoice_id>/", views.get_expenses, name="get_expenses"),
    path(
        "expenses/<uuid:invoice_id>/create/",
        views.create_expenses,
        name="create_expenses",
    ),
    path(
        "expenses/<uuid:expenses_id>/update/",
        views.update_expenses,
        name="update_expenses",
    ),
    path(
        "expenses/<uuid:expenses_id>/delete/",
        views.delete_expenses,
        name="delete_expenses",
    ),
]

# CLIENTS URLS
urlpatterns += [
    path("clients/", views.get_clients, name="get_clients"),
    path("clients/create/", views.create_client, name="create_client"),
    path("clients/sync/", views.get_accounting_clients, name="get_accounting_clients"),
    path("clients/<uuid:client_id>/", views.get_client, name="get_client"),
    path(
        "clients/<uuid:client_id>/update/",
        views.update_client,
        name="update_client",
    ),
    path(
        "clients/<uuid:client_id>/sync/",
        views.sync_client,
        name="sync_client",
    ),
    path("clients/<uuid:client_id>/delete/", views.delete_client, name="delete_client"),
]

# PROPOSAL URLS
urlpatterns += [
    path(
        "proposals/<uuid:client_id>/create/",
        views.create_proposal,
        name="create_proposal",
    ),
    path(
        "proposals/<uuid:proposal_id>/update/",
        views.update_proposal,
        name="update_proposal",
    ),
    path(
        "proposals/<uuid:proposal_id>/delete/",
        views.delete_proposal,
        name="delete_proposal",
    ),
    path(
        "proposals/<uuid:proposal_id>/download/",
        views.download_proposal,
        name="download_proposal",
    ),
    path(
        "proposals/<uuid:proposal_id>/send/",
        views.send_proposal,
        name="send_proposal",
    ),
    path(
        "proposals/<uuid:proposal_id>/view/",
        views.client_sign_proposal,
        name="client_sign_proposal",
    ),
]

# RECURRING INVOICE URLS
urlpatterns += [
    path("invoices/", views.create_invoice, name="create_invoice"),
    path("invoices/list/", views.get_invoices, name="get_invoices"),
    path(
        "invoices/archive-list/", views.get_archived_invoices, name="get_archive_list"
    ),
    path("invoices/manage/", views.manage_invoices, name="manage_invoices"),
    path("invoices/<uuid:invoice_id>/", views.get_invoice, name="get_single_invoice"),
    path("invoices/<uuid:invoice_id>/edit/", views.edit_invoice, name="edit_invoice"),
    path(
        "invoices/<uuid:invoice_id>/pause/", views.pause_invoice, name="pause_invoice"
    ),
    path(
        "invoices/<uuid:invoice_id>/new-hours/",
        views.invoice_add_hours,
        name="invoice_add_hours",
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
        "invoices/<uuid:invoice_id>/update/next-date/",
        views.update_invoice_next_date,
        name="update_invoice_next_date",
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
        "invoices/<uuid:archive_invoice_id>/feedback/",
        views.invoice_feedback,
        name="invoice_feedback",
    ),
    path(
        "invoices/<uuid:invoice_id>/details/",
        views.view_invoice_details,
        name="view_invoice_details",
    ),
]

# SINGLE INVOICE URLS
urlpatterns += [
    path("invoices/single/", views.create_single_invoice, name="single_invoice"),
    path(
        "invoices/single/<uuid:single_invoice_id>/",
        views.update_single_invoice,
        name="update_single_invoice",
    ),
    path(
        "invoices/single/<uuid:single_invoice_id>/sync",
        views.sync_single_invoice,
        name="sync_single_invoice",
    ),
    path(
        "invoices/single/<uuid:single_invoice_id>/send/",
        views.send_single_invoice_email,
        name="send_single_invoice_email",
    ),
    path(
        "invoices/single/<uuid:single_invoice_id>/send-installment/",
        views.send_first_installment,
        name="send_invoice_installment",
    ),
    path(
        "invoices/single/<uuid:single_invoice_id>/status/",
        views.update_single_invoice_status,
        name="update_single_invoice_status",
    ),
    path(
        "invoices/single/<uuid:single_invoice_id>/qrcode/",
        views.generate_qrcode_single_invoice,
        name="generate_qrcode_single_invoice",
    ),
    path(
        "invoices/single-line-item/",
        views.single_invoice_line_item,
        name="single_invoice_line_item",
    ),
]

# SENT INVOICE URLS
urlpatterns += [
    path(
        "sent_invoices/<uuid:sent_invoice_id>/",
        views.get_sent_invoice,
        name="get_sent_invoice",
    ),
    path(
        "sent_invoices/<uuid:sent_invoice_id>/remind/",
        views.resend_invoice_email,
        name="resend_invoice_email",
    ),
    path(
        "sent_invoices/<uuid:invoice_id>/sent_invoices/",
        views.sent_invoices_list,
        name="sent_invoices_list",
    ),
    path(
        "sent_invoices/<uuid:sent_invoice_id>/sync/sent_invoice/",
        views.sync_sent_invoice,
        name="sync_sent_invoice",
    ),
    path(
        "sent_invoices/<uuid:sent_invoice_id>/cancel/",
        views.cancel_invoice,
        name="cancel_invoice",
    ),
    path(
        "sent_invoices/<uuid:sent_invoice_id>/edit_hours/",
        views.edit_sent_invoice_hours,
        name="edit_sent_invoice_hours",
    ),
    path(
        "sent_invoices/<uuid:sent_invoice_id>/download/",
        views.download_sent_invoice_copy,
        name="download_sent_invoice",
    ),
    path(
        "sent_invoices/<uuid:sent_invoice_id>/qrcode/",
        views.generate_qrcode_invoice,
        name="generate_qrcode_invoice",
    ),
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
    path("accounting-sync/", views.accounting_sync, name="accounting_sync"),
]


# STRIPE URLS
urlpatterns += [
    path(
        "stripe-standard-webhook/", views.stripe_standard_webhook, name="stripe_webhook"
    ),
    path(
        "stripe-connect-webhook/", views.stripe_connect_webhook, name="stripe_webhook"
    ),
    path(
        "invoice-payment/<uuid:sent_invoice_id>/", views.pay_invoice, name="pay_invoice"
    ),
    path(
        "invoice-payment/<str:email_id>/",
        views.pay_invoice_email,
        name="pay_invoice_email",
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
    path("timer/start/", views.start_timer, name="start_timer"),
    path("timer/pause/", views.pause_timer, name="pause_timer"),
    path("timer/stop/", views.stop_timer, name="stop_timer"),
    path("timer/resume/", views.resume_timer, name="resume_timer"),
    path("timer/reset/", views.reset_timer, name="reset_timer"),
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
