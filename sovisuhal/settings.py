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
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'handlers': {
            'filedeb': {
                'level': 'DEBUG',
                'class': 'logging.FileHandler',
                'filename': '/data/logs/django/debug.log',
            },
            'fileinf': {
                'level': 'DEBUG',
                'class': 'logging.FileHandler',
                'filename': '/data/logs/django/debuginf.log',
            },
        },
        'loggers': {
            'django': {
                'handlers': ['filedeb'],
                'level': 'DEBUG',
                'propagate': True,
            },
            'django.template': {
                'handlers': ['fileinf'],
                'level': 'INFO',
                'propagate': True,
            },
        },
    }
else:
    SECRET_KEY = 'zs6fmh=6x4+n48zn02mfw8+vd(6dh#+9_d8$)4o=e^&0p2yp$)'
    DEBUG = 'False'#'True'

# SECURITY WARNING: don't run with debug turned on in production!



# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'widget_tweaks',
    'uniauth',
    'celery',
    'celery_progress',
    'elasticHal',
    'corsheaders',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    #'csp.middleware.CSPMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

CORS_ALLOWED_ORIGINS = [
    "https://sovisu.univ-tln.fr",
    "https://sovisu.univ-tln.fr:9200",
    "https://sovisu.univ-tln.fr:5601",
    "https://sovisu.univ-tln.fr:6379",
    "http://192.168.0.65:*",
    "http://localhost:*",
    "http://localhost:9200",
    "http://localhost:5601",
    "http://localhost:6379",
    "http://127.0.0.1:*",
    "http://127.0.0.1:9200",
    "http://127.0.0.1:5601",
    "http://127.0.0.1:6379",
    "http://sovisu.dynalias.org",
    "http://sovisu.dynalias.org:9200"
    "http://sovisu.dynalias.org:5601",
    "http://sovisu.dynalias.org:6379"

]
#ALLOWED_HOSTS = ["sovisu.univ-tln.fr", "localhost"]
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '192.168.0.65', 'sovisu.dynalias.org', 'DR','[::1]']

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOWED_ORIGINS = [
    "https://sovisu.univ-tln.fr",
    "https://sovisu.univ-tln.fr:9200",
    "https://sovisu.univ-tln.fr:5601",
    "https://sovisu.univ-tln.fr:6379",
    "http://localhost",
    "http://localhost:9200",
    "http://localhost:5601",
    "http://localhost:6379",
    "http://192.168.0.65",
    "http://192.168.0.65:5601",
    "http://192.168.0.65:6379",
    "http://127.0.0.1",
    "http://127.0.0.1:9200",
    "http://127.0.0.1:5601",
    "http://127.0.0.1:6379",
    "http://sovisu.dynalias.org",
    "http://sovisu.dynalias.org:5601",
    "http://sovisu.dynalias.org:6379"

]


SECURE_CROSS_ORIGIN_OPENER_POLICY=None

CORS_URLS_REGEX = r"^/app/*"
CORS_ALLOW_ALL_ORIGINS = True

SECURE_REFERRER_POLICY = 'origin'

#test CSP
# info : https://book.hacktricks.xyz/pentesting-web/content-security-policy-csp-bypass
# djnago specs :
Bibi = ["'self' 'unsafe-inline' 'unsafe-eval'"]
Dns = ["http://localhost", "http://localhost:*", "http://127.0.0.1:*",]
# BibiSha =  ["'self' 'sha256-r5bInLZa0y6YxHFpmz7cjyYrndjwCeDLDu/1KeMikHA='"]
# BibiScripts =  Bibi  + Dns
# Scripts = [
#     "https://cdn.datatables.net",
#     "https://cdn.jsdelivr.net",
#     "https://code.jquery.com",
#     "https://cdnjs.cloudflare.com",
#     "http://cdnjs.cloudflare.com",
#     "https://d3js.org",
#     "https://unpkg.com",]
#
# Styles = ["https://cdn.datatables.net","https://cdn.jsdelivr.net","https://rsms.me","https://unpkg.com",] + Dns
# Polices = ["https://rsms.me",]
# CSP_DEFAULT_SRC = Bibi + Dns
# CSP_IMG_SRC = Bibi  + Dns
# CSP_FRAME_SRC = BibiScripts  + Dns
# CSP_STYLE_SRC = Bibi + Styles
# CSP_SCRIPT_SRC = BibiScripts + Scripts
# CSP_FONT_SRC = Bibi + Polices + Dns
#
# CSP_BASE_URI = Bibi
# CSP_FRAME_ANCESTORS = Bibi + Dns
# CSP_FORM_ACTION = Bibi
# CSP_INCLUDE_NONCE_IN = ('script-src', ) #oblige a modifier tous les templates pour envoyer un nonce 'context processor" https://www.laac.dev/blog/content-security-policy-using-django/
# CSP_MANIFEST_SRC = Bibi
# CSP_WORKER_SRC = Bibi
# CSP_MEDIA_SRC = Bibi



#X_FRAME_OPTIONS = 'ALLOW-FROM ' + " " .join(Dns)
X_FRAME_OPTIONS = 'sameorigin'

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
            # 'libraries': {
            #         'csp': 'csp.templatetags.csp',
            #     },
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

STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles') #'/data/SoVisu/staticfiles/
STATIC_URL = '/static/'
STATICFILES_DIRS = (os.path.join(BASE_DIR,'static'),)
# Pas sûr sur çà... J'ai l'impression qu'il y a deux zones de fichiers statiques
# j'ai eu un stock de "Found another file with the destination path"


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
EMAIL_SUBJECT_PREFIX = '[SoVisu]'

ADMINS = (
    ('Sovisuhal', 'dreymond@univ-tln.fr'),
    # pour rajouter un profil:
    # ('role utilisateur', 'mail'),
    ('Sovisuhal1', '')
)

MANAGERS = (
    ('BU', 'dreymond@univ-tln.fr'),  # changer l'adresse
    ('BU_1', '')
)
# Attention ! La liste Admin a besoin d'avoir un minimum de 2 profils renseignés. Dans le cas où un seul admin est présent pour le système, merci de laisser le 2e profil sans adresse mail renseignée.

# Celery Settings
BROKER_URL = 'redis://localhost:6379'
CELERY_RESULT_BACKEND = 'redis://localhost:6379'

