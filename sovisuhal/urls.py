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
from decouple import config

# from django.views.static import serve
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path, re_path

from . import view_cbv, viewsActions

mode = config("mode")

if mode == "dev":
    root_document = settings.STATICFILES_DIRS
else:
    root_document = settings.STATIC_ROOT


urlpatterns = [
    path(
        "admin/logout/", lambda request: redirect("/accounts/logout/", permanent=False)
    ),  # is before admin.site.urls to override. Return to uniauth logout instead default redirect.
    path("admin/", admin.site.urls),
    re_path(r"^celery-progress/", include("celery_progress.urls")),  # the endpoint is configurable
    path("", viewsActions.admin_access_login, name="login"),
    # path("create/", views.create, name="creation"),
    # path("check/", views.check, name="check"),
    # path("index/", views.index, name="index"),
    # path("dashboard/", views.dashboard, name="dashboard"),
    # path("references/", views.references, name="references"),
    # path("terminology/", views.terminology, name="terminology"),
    # path("terminology/", views.terminology, name="terminology"),
    # path("terminology/", views.terminology, name="terminology"),
    # path("wordcloud/", views.wordcloud, name="wordcloud"),
    # path("tools/", views.tools, name="tools"),
    # path("search/", views.search, name="search"),
    # path("presentation/", views.presentation, name="presentation"),
    # path("faq/", views.faq, name="faq"),
    # path("ressources/", views.ressources, name="ressources"),
    # path("unknown/", views.unknown, name="unknown"),
    # path("CreateCredentials/", viewsActions.create_credentials, name="credentials"),
    path("create/", view_cbv.CreateView.as_view(), name="create"),
    path("check/", view_cbv.CheckView.as_view(), name="check"),
    path("index/", view_cbv.IndexView.as_view(), name="index"),
    path("dashboard/", view_cbv.DashboardView.as_view(), name="dashboard"),
    path("references/", view_cbv.ReferencesView.as_view(), name="references"),
    path("terminology/", view_cbv.TerminologyView.as_view(), name="terminology"),
    path("lexicon/", view_cbv.LexiconView.as_view(), name="lexicon"),
    path("tools/", view_cbv.ToolsView.as_view(), name="tools"),
    path("search/", view_cbv.SearchView.as_view(), name="search"),
    path("presentation/", view_cbv.PresentationView.as_view(), name="presentation"),
    path("faq/", view_cbv.FAQView.as_view(), name="faq"),
    path("ressources/", view_cbv.RessourcesView.as_view(), name="ressources"),
    path("unknown/", view_cbv.UnknownView.as_view(), name="unknown"),
    path(
        "validate_credentials/",
        viewsActions.validate_credentials,
        name="validate_credentials",
    ),
    path(
        "refresh-aurehal-id/",
        viewsActions.refresh_aurehal_id,
        name="refresh-aurehal-id",
    ),
    path("update_authorship/", viewsActions.update_authorship, name="update_authorship"),
    path("update_members/", viewsActions.update_members, name="update_members"),
    path(
        "validate_references/",
        viewsActions.validate_references,
        name="validate_references",
    ),
    path(
        "validate_expertise/",
        viewsActions.validate_expertise,
        name="invalidate_concepts",
    ),
    path(
        "validate_guiding-domains/",
        viewsActions.validate_guiding_domains,
        name="validate_guiding-domains",
    ),
    # path(
    #     "validate_research-description/",
    #     viewsActions.validate_research_description,
    #     name="validate_research-description",
    # ),
    path("export_hceres_xls/", viewsActions.export_hceres_xls, name="export_hceres_xls"),
    path("accounts/", include("uniauth.urls", namespace="uniauth")),
    path("tinymce/", include("tinymce.urls")),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
