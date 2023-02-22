"""
Django settings for sovisuhal project.

Generated by 'django-admin startproject' using Django 3.1.5.

For more information on this file, see
https://docs.djangoproject.com/en/3.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.1/ref/settings/
"""

import os
from pathlib import Path

from decouple import config

mode = config("mode")

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.1/howto/deployment/checklist/
# with open ('../config/SoVisu/secretDjango', 'r') as fic:
#     SECRET_KEY = fic.read()
#     SECRET_KEY = SECRET_KEY .strip()
# SECURITY WARNING: keep the secret key used in production secret!

SECRET_KEY = "zs6fmh=6x4+n48zn02mfw8+vd(6dh#+9_d8$)4o=e^&0p2yp$)"
STATIC_URL = '/static/'
if mode == "Prod":
    SECRET_KEY = config("DjangoKey")
    DEBUG = eval(config("DJANGO_DEBUG"))
    # Settings used by Uniauth
    LOGIN_URL = "/accounts/login/"
    # PASSWORD_RESET_TIMEOUT_DAYS = 3
    UNIAUTH_ALLOW_SHARED_EMAILS = True
    UNIAUTH_ALLOW_STANDALONE_ACCOUNTS = True
    UNIAUTH_FROM_EMAIL = "sovisu@univ-tln.fr"
    UNIAUTH_LOGIN_DISPLAY_STANDARD = True
    UNIAUTH_LOGIN_DISPLAY_CAS = True
    UNIAUTH_LOGIN_REDIRECT_URL = "/"  # +  uniauth_profile.accounts
    UNIAUTH_LOGOUT_CAS_COMPLETELY = True
    UNIAUTH_LOGOUT_REDIRECT_URL = None
    UNIAUTH_MAX_LINKED_EMAILS = 20
    UNIAUTH_PERFORM_RECURSIVE_MERGING = True
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "handlers": {
            "filedeb": {
                "level": "DEBUG",
                "class": "logging.FileHandler",
                "filename": "/data/logs/django/debug.log",
            },
            "fileinf": {
                "level": "DEBUG",
                "class": "logging.FileHandler",
                "filename": "/data/logs/django/debuginf.log",
            },
        },
        "loggers": {
            "django": {
                "handlers": ["filedeb"],
                "level": "DEBUG",
                "propagate": True,
            },
            "django.template": {
                "handlers": ["fileinf"],
                "level": "INFO",
                "propagate": True,
            },
        },
    }
    STATIC_ROOT = os.path.join('/data/SoVisu/staticfiles/')  # '/data/SoVisu/staticfiles/
    STATICFILES_DIRS = (os.path.join(BASE_DIR, 'staticfiles'),)
    BROKER_URL = "redis://sovisu.univ-tln.fr:6379/0"
    CELERY_RESULT_BACKEND = "redis://sovisu.univ-tln.fr:6379/0"
else:
    SECRET_KEY = "zs6fmh=6x4+n48zn02mfw8+vd(6dh#+9_d8$)4o=e^&0p2yp$)"
    DEBUG = True
    STATICFILES_DIRS = (os.path.join(BASE_DIR, "static/"),)
    # Celery Settings
    CELERY_BROKER_URL = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND = "redis://localhost:6379/0"
# SECURITY WARNING: don't run with debug turned on in production!

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "widget_tweaks",
    "uniauth",
    "celery",
    "celery_progress",
    "elasticHal",
    "corsheaders",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    #'csp.middleware.CSPMiddleware',
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

CORS_ALLOWED_ORIGINS = [
    "https://sovisu.univ-tln.fr",
    "https://sovisu.univ-tln.fr:9200",
    "https://sovisu.univ-tln.fr:5601",
    "https://sovisu.univ-tln.fr:6379",
    "http://194.214.84.14:*",
    "http://localhost:*",
    "http://localhost:9200",
    "http://localhost:5601",
    "http://localhost:6379",
    "http://127.0.0.1:*",
    "http://127.0.0.1:9200",
    "http://127.0.0.1:5601",
    "http://127.0.0.1:6379",
]

# ALLOWED_HOSTS = ["sovisu.univ-tln.fr", "localhost"]
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "194.214.84.14", "sovisu.univ-tln.fr"]
CSRF_TRUSTED_ORIGINS = ["https://194.214.84.14", "https://localhost"]

CORS_ALLOW_CREDENTIALS = True

SECURE_CROSS_ORIGIN_OPENER_POLICY = None

CORS_URLS_REGEX = r"^/app/*"
CORS_ALLOW_ALL_ORIGINS = True

SECURE_REFERRER_POLICY = "origin"

# test CSP
# info : https://book.hacktricks.xyz/pentesting-web/content-security-policy-csp-bypass
# djnago specs :
Dns = [
    "http://localhost",
    "http://localhost:*",
    "http://127.0.0.1:*",
]

X_FRAME_OPTIONS = "sameorigin"


AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "uniauth.backends.CASBackend",
]

ROOT_URLCONF = "sovisuhal.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            # 'libraries': {
            #         'csp': 'csp.templatetags.csp',
            #     },
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "sovisuhal.wsgi.application"

# Database
# https://docs.djangoproject.com/en/3.1/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Password validation
# https://docs.djangoproject.com/en/3.1/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/3.1/topics/i18n/

LANGUAGE_CODE = "fr"

TIME_ZONE = "Europe/Paris"

USE_I18N = True

USE_L10N = True

USE_TZ = True

# EMAIL Setup
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False
EMAIL_PORT = 587

EMAIL_HOST_USER = "testsovis@gmail.com"
EMAIL_HOST_PASSWORD = config("mailSovisu")

SERVER_EMAIL = EMAIL_HOST_USER
EMAIL_SUBJECT_PREFIX = "[SoVisu]"

ADMINS = (
    ("Sovisuhal", "dreymond@univ-tln.fr"),
    # pour rajouter un profil:
    # ('role utilisateur', 'mail'),
    ("Sovisuhal1", ""),
)

MANAGERS = (("BU", "dreymond@univ-tln.fr"), ("BU_1", ""))  # changer l'adresse
# Attention ! La liste Admin a besoin d'avoir un minimum de 2 profils renseignés.
# Dans le cas où un seul admin est présent pour le système,
# merci de laisser le 2e profil sans adresse mail renseignée.


