"""
Django settings for sovisuhal project.

Generated by 'django-admin startproject' using Django 3.1.5.

For more information on this file, see
https://docs.djangoproject.com/en/3.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.1/ref/settings/
"""

from pathlib import Path
import os
from decouple import config

mode = config('mode')

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.1/howto/deployment/checklist/
# with open ('../config/SoVisu/secretDjango', 'r') as fic:
#     SECRET_KEY = fic.read()
#     SECRET_KEY = SECRET_KEY .strip()
# SECURITY WARNING: keep the secret key used in production secret!

SECRET_KEY = 'zs6fmh=6x4+n48zn02mfw8+vd(6dh#+9_d8$)4o=e^&0p2yp$)'

if mode == 'Prod':
    SECRET_KEY = config('DjangoKey')
    DEBUG = config('DJANGO_DEBUG')
    # Settings used by Uniauth
    LOGIN_URL = '/accounts/login/'
    # PASSWORD_RESET_TIMEOUT_DAYS = 3
    UNIAUTH_ALLOW_SHARED_EMAILS = True
    UNIAUTH_ALLOW_STANDALONE_ACCOUNTS = True
    UNIAUTH_FROM_EMAIL = 'sovisu@univ-tln.fr'
    UNIAUTH_LOGIN_DISPLAY_STANDARD = True
    UNIAUTH_LOGIN_DISPLAY_CAS = True
    UNIAUTH_LOGIN_REDIRECT_URL = '/'  # +  uniauth_profile.accounts
    UNIAUTH_LOGOUT_CAS_COMPLETELY = True
    UNIAUTH_LOGOUT_REDIRECT_URL = None
    UNIAUTH_MAX_LINKED_EMAILS = 20
    UNIAUTH_PERFORM_RECURSIVE_MERGING = True
else:
    SECRET_KEY = 'zs6fmh=6x4+n48zn02mfw8+vd(6dh#+9_d8$)4o=e^&0p2yp$)'
    DEBUG = 'True'

# SECURITY WARNING: don't run with debug turned on in production!

ALLOWED_HOSTS = ['*']

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'widget_tweaks',
    'uniauth'  # ,
    # 'celery',
    # 'celery_progress'
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'uniauth.backends.CASBackend',
]

ROOT_URLCONF = 'sovisuhal.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates']
        ,
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'sovisuhal.wsgi.application'

# Database
# https://docs.djangoproject.com/en/3.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Password validation
# https://docs.djangoproject.com/en/3.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
# https://docs.djangoproject.com/en/3.1/topics/i18n/

LANGUAGE_CODE = 'fr'

TIME_ZONE = 'Europe/Paris'

USE_I18N = True

USE_L10N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.1/howto/static-files/

STATIC_URL = '/static/'
STATICFILES_DIRS = (os.path.join('static'),)
# Pas sûr sur çà... J'ai l'impression qu'il y a deux zones de fichiers statiques
# j'ai eu un stock de "Found another file with the destination path"
STATIC_ROOT = '/data/SoVisu/staticfiles/'

# EMAIL Setup
# https://docs.djangoproject.com/en/3.1/topics/email/

# EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
# EMAIL_HOST = 'smtp.yourserver.com'
# EMAIL_PORT = '<your-server-port>'
# EMAIL_HOST_USER = 'your@djangoapp.com'
# EMAIL_HOST_PASSWORD = 'your-email account-password'
# EMAIL_USE_TLS = True
# EMAIL_USE_SSL = False

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False
EMAIL_PORT = 587
EMAIL_HOST_USER = 'testsovis@gmail.com'
EMAIL_HOST_PASSWORD = 'ckpfbawohpgrhykz'
SERVER_EMAIL = EMAIL_HOST_USER

ADMINS = (
    ('Sovisuhal', 'dreymond@univ-tln.fr'),
    #pour rajouter un profil:
    #('role utilisateur', 'mail'),
    ('Sovisuhal1', '')
)
#Attention! La liste Admin a besoin d'avoir un minimum de 2 profil renseignés. Dans le cas ou un seul admin est présent pour le système, merci de laisser le 2ème profil sans adresse mail renseignée.