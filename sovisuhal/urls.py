"""sovisuhal URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.conf.urls import include

from . import views

urlpatterns = [
    path('admin/', admin.site.urls),

    path('', views.index, name='index'),

    path('index/', views.cs_index, name='cs_index'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('publicationboard/', views.publicationboard, name='publicationboard'),
    path('references/', views.references, name='references'),

    path('terminology/', views.terminology, name='terminology'),

    path('wordcloud/', views.wordcloud, name='wordcloud'),

    path('check/', views.check, name='check'),

    path('search/', views.search, name='search'),

    path('faq/', views.faq, name='faq'),
    path('ressources/', views.ressources, name='ressources'),
    path('tools/', views.tools, name='tools'),
    path('contact/', views.contact, name='contact'),

    path('help/', views.help, name='help'),
    path('CreateCredentials/', views.CreateCredentials, name='credentials'),
    path('validate_credentials/', views.validateCredentials, name='validate_credentials'),
    path('validate_references/', views.validateReferences, name='validate_references'),
    path('invalidate_concepts/', views.invalidateConcept, name='invalidate_concepts'),
    path('validate_guiding-domains/', views.validateGuidingDomains, name='validate_guiding-domains'),
    path('validate_guiding-keywords/', views.validateGuidingKeywords, name='validate_guiding-keywords'),
    path('presentation/', views.presentation, name='presentation'),
    path('unknown/', views.unknown, name='unknown'),
    path('create/', views.create, name='creation'),
    path('accounts/', include('uniauth.urls', namespace='uniauth')),
    path('loggedin/', views.loggedin, name='loggued')

]
