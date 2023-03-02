from datetime import datetime

# from django.shortcuts import redirect, render
from django.views.generic import TemplateView

# from . import forms, viewsActions
from .libs import esActions  # , halConcepts

# from uniauth.decorators import login_required

# from sovisuhal.views import default_checker, get_date, get_scope_data


es = esActions.es_connector()


class CommonContextMixin:
    """
    Mixin to provide common context variables to all views
    """

    def setup(self, request, *args, **kwargs):
        self.request = request
        return super().setup(request, *args, **kwargs)

    def get_regular_parameters(self, request):
        """
        Get the regular GET parameters from the request
        """
        if "struct" in request.GET:
            struct = request.GET["struct"]
        else:
            struct = -1

        if "type" in request.GET:
            i_type = request.GET["type"]
        else:
            i_type = -1

        if "id" in request.GET:
            p_id = request.GET["id"]
        else:
            p_id = -1

        if "ldapid" in request.GET:
            ldapid = request.GET["ldapid"]
        else:
            ldapid = None

        return struct, i_type, p_id, ldapid

    def get_date(self, request):
        start_date = "2000"

        if "from" in request.GET:
            date_from = request.GET["from"]
        else:
            date_from = f"{start_date[0:4]}-01-01"

        if "to" in request.GET:
            date_to = request.GET["to"]
        else:
            date_to = datetime.today().strftime("%Y-%m-%d")

        return date_from, date_to

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        (
            context["struct"],
            context["type"],
            context["id"],
            context["ldapid"],
        ) = self.get_regular_parameters(self.request)
        context["from"], context["to"] = self.get_date(self.request)

        return context


class IndexView(CommonContextMixin, TemplateView):
    template_name = "index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get parameters
        indexcat = self.request.GET.get("indexcat")
        indexstruct = self.request.GET.get("indexstruct")

        scope_param = esActions.scope_all()
        # création dynamique des tabs sur la page à partir de struct_tab
        struct_tab = es.search(
            index="*-structures",
            body=scope_param,
            filter_path=["hits.hits._source.structSirene, hits.hits._source.acronym"],
        )
        struct_tab = [hit["_source"] for hit in struct_tab["hits"]["hits"]]

        indextype = ""
        if indexcat == "lab":
            indextype = "*-laboratories"
        elif indexcat == "rsr":
            indextype = "*-researchers"

        count = es.count(index=f"{indexstruct}{indextype}", body=scope_param)["count"]
        res = es.search(index=f"{indexstruct}{indextype}", body=scope_param, size=count)
        cleaned_entities = [hit["_source"] for hit in res["hits"]["hits"]]

        if indexcat == "lab":
            cleaned_entities = sorted(cleaned_entities, key=lambda k: k["acronym"])
        elif indexcat == "rsr":
            cleaned_entities = sorted(cleaned_entities, key=lambda k: k["lastName"])

        context["indexcat"] = indexcat
        context["indexstruct"] = indexstruct
        context["entities"] = cleaned_entities
        context["struct_tab"] = struct_tab

        if context["type"] == -1 and context["id"] == -1:
            del context["type"]
            del context["id"]
            del context["struct"]

        return context


class FAQView(CommonContextMixin, TemplateView):
    template_name = "faq.html"


class RessourcesView(CommonContextMixin, TemplateView):
    template_name = "ressources.html"


class PresentationView(CommonContextMixin, TemplateView):
    template_name = "presentation.html"


class UnknownView(TemplateView):
    template_name = "404.html"
