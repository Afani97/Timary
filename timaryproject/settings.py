"""
Django settings for timaryproject project.

Generated by 'django-admin startproject' using Django 3.2.8.

For more information on this file, see
https://docs.djangoproject.com/en/3.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.2/ref/settings/
"""
import os
import sys
from pathlib import Path

from decouple import config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

AUTH_USER_MODEL = "timary.User"

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config("SECRET_KEY", default="abc123")

DEBUG = config("DEBUG", default=True, cast=bool)

ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS", default="*", cast=lambda v: [s.strip() for s in v.split(",")]
)

SITE_URL = "http://127.0.0.1:8000"


# Application definition

INSTALLED_APPS = [
    # TIMARY
    "timary",
    # DJANGO
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    # WHITENOISE
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    # 3RD PARTY
    "django_q",
    "django_twilio",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "csp.middleware.CSPMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "timaryproject.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "timary.context_processors.site_url",
            ],
        },
    },
]

WSGI_APPLICATION = "timaryproject.wsgi.application"


# Database
# https://docs.djangoproject.com/en/3.2/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

if not DEBUG:
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_SSL_REDIRECT = True


# Password validation
# https://docs.djangoproject.com/en/3.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/3.2/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "America/New_York"

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.2/howto/static-files/

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

# Login Redirect
LOGIN_URL = "/login/"
LOGOUT_REDIRECT_URL = "/login/"
LOGIN_REDIRECT_URL = ""

# DJANGO Q
Q_CLUSTER = {
    "name": "DjangORM",
    "workers": 4,
    "timeout": 90,
    "retry": 120,
    "queue_limit": 50,
    "bulk": 10,
    "orm": "default",
    "sync": False,
}

# EMAIL
DEFAULT_FROM_EMAIL = (
    f"Ari From Timary <{config('NAMECHEAP_EMAIL', default='test@test.com')}>"
)
EMAIL_HOST = "mail.privateemail.com"
EMAIL_PORT = 587
EMAIL_HOST_USER = config("NAMECHEAP_EMAIL", default="test@test.com")
EMAIL_HOST_PASSWORD = config("NAMECHEAP_PASSWORD", default="abc123")
EMAIL_USE_TLS = True

# Content Security Policy
CSP_DEFAULT_SRC = ("'none'",)
CSP_STYLE_SRC = (
    "'self'",
    "'unsafe-inline'",
    "https://cdn.jsdelivr.net/npm/daisyui@1.16.1/dist/full.css",
    "https://cdnjs.cloudflare.com/ajax/libs/tailwindcss/2.2.19/tailwind.min.css",
)
CSP_SCRIPT_SRC = (
    "'self'",
    "'unsafe-eval'",
    "'nonce-base'",
    "'nonce-pay-invoice'",
    "'nonce-clear-hours-modal'",
    "'nonce-clear-invoice-modal'",
    "https://unpkg.com/htmx.org@1.5.0",
    "https://js.stripe.com",
)
CSP_IMG_SRC = ("'self'",)
CSP_FONT_SRC = ("'self'",)
CSP_CONNECT_SRC = (
    "'self'",
    "https://api.stripe.com",
)
CSP_OBJECT_SRC = ("'none'",)
CSP_BASE_URI = ("'none'",)
CSP_FRAME_SRC = (
    "'self'",
    "https://js.stripe.com",
    "https://hooks.stripe.com",
)
CSP_FRAME_ANCESTORS = ("'none'",)
CSP_FORM_ACTION = ("'self'",)
CSP_INCLUDE_NONCE_IN = ("script-src",)
CSP_MEDIA_SRC = ("'self'",)

# WHITENOISE
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"


# TWILIO
TWILIO_ACCOUNT_SID = config("TWILIO_ACCOUNT_SID", default="abc123")
TWILIO_AUTH_TOKEN = config("TWILIO_AUTH_TOKEN", default="abc123")
TWILIO_PHONE_NUMBER = config("TWILIO_PHONE_NUMBER", default="+17742613186")
TWILIO_DEFAULT_CALLERID = "Aristotel Fani"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# STRIPE
STRIPE_PUBLIC_API_KEY = config("STRIPE_PUBLIC_API_KEY", default="abc123")
STRIPE_SECRET_API_KEY = config("STRIPE_SECRET_API_KEY", default="abc123")


if "test" in sys.argv or os.environ.get("GITHUB_WORKFLOW"):
    DEBUG = True
    Q_CLUSTER["sync"] = True
    EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    PASSWORD_HASHERS = [
        "django.contrib.auth.hashers.MD5PasswordHasher",
    ]
