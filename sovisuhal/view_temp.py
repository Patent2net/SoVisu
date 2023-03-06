from datetime import datetime

from django.shortcuts import redirect  # , render
from django.views.generic import TemplateView
from elasticsearch import BadRequestError

from sovisuhal.views import get_scope_data

from . import viewsActions
from .libs import esActions  # , halConcepts

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


class DashboardView(CommonContextMixin, TemplateView):
    template_name = "dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        (
            entity,
            hastoconfirm,
            filtrechercheur,
            filtre_lab_a,
            filtre_lab_b,
            url,
            dash,
        ) = self.get_elastic_data(context["type"], context["id"], context["struct"])

        context["dash"] = dash
        context["entity"] = entity
        context["hastoconfirm"] = hastoconfirm
        context["filterRsr"] = filtrechercheur
        context["filterlabA"] = filtre_lab_a
        context["filterlabB"] = filtre_lab_b
        context["url"] = url

        return context

    def get_elastic_data(self, i_type, p_id, struct):
        # Get scope data
        key, search_id, index_pattern, ext_key, scope_param = get_scope_data(i_type, p_id)

        res = es.search(index=f"{struct}-{search_id}{index_pattern}", body=scope_param)
        # on pointe sur index générique, car pas de LabHalId ?
        try:
            entity = res["hits"]["hits"][0]["_source"]
        except (IndexError, BadRequestError):
            return redirect("unknown")
        # /

        hastoconfirm = False

        validate = False
        if i_type == "rsr":
            field = "authIdHal_s"
            hastoconfirm_param = esActions.confirm_p(field, entity["halId_s"], validate)

        elif i_type == "lab":
            field = "labStructId_i"
            hastoconfirm_param = esActions.confirm_p(field, entity["halStructId"], validate)
        else:
            return redirect("unknown")

        if es.count(index=f"{struct}*-documents", body=hastoconfirm_param)["count"] > 0:
            hastoconfirm = True

        dash = ""
        if i_type == "rsr":
            indexsearch = f"{struct}-{entity['labHalId']}-researchers-{entity['ldapId']}-documents"
            filtrechercheur = f'_index: "{indexsearch}"'
            filtre_lab_a = ""
            filtre_lab_b = ""
        elif i_type == "lab":
            if "dash" in self.request.GET:
                dash = self.request.GET["dash"]
            else:
                dash = "membres"
            filtrechercheur = ""
            filtre_lab_a = f'harvested_from_ids: "{p_id}"'
            filtre_lab_b = f'labHalId.keyword: "{p_id}"'
        else:
            return redirect("unknown")

        url = viewsActions.vizualisation_url()

        return entity, hastoconfirm, filtrechercheur, filtre_lab_a, filtre_lab_b, url, dash


class ReferencesView(CommonContextMixin, TemplateView):
    template_name = "references.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if "filter" in self.request.GET:
            context["filter"] = self.request.GET["filter"]
        else:
            context["filter"] = -1

        entity, hastoconfirm, references_cleaned = self.get_elastic_data(
            context["type"],
            context["id"],
            context["struct"],
            context["filter"],
            context["from"],
            context["to"],
        )

        context["entity"] = entity
        context["hastoconfirm"] = hastoconfirm
        context["references"] = references_cleaned
        return context

    def get_elastic_data(self, i_type, p_id, struct, i_filter, date_from, date_to):
        # Get scope data
        key, search_id, index_pattern, ext_key, scope_param = get_scope_data(i_type, p_id)
        res = es.search(index=f"{struct}-{search_id}{index_pattern}", body=scope_param)

        try:
            entity = res["hits"]["hits"][0]["_source"]
        except IndexError:
            return redirect("unknown")

        hastoconfirm = False
        field = "harvested_from_ids"
        validate = False
        if i_type == "rsr":
            hastoconfirm_param = esActions.confirm_p(field, entity["halId_s"], validate)

            if (
                es.count(
                    index=f"{struct}-{entity['labHalId']}-researchers-{entity['ldapId']}-documents",
                    body=hastoconfirm_param,
                )["count"]
                > 0
            ):
                hastoconfirm = True
        if i_type == "lab":
            hastoconfirm_param = esActions.confirm_p(field, entity["halStructId"], validate)

            if (
                es.count(
                    index=f"{struct}-{entity['halStructId']}-laboratories-documents",
                    body=hastoconfirm_param,
                )["count"]
                > 0
            ):
                hastoconfirm = True

        # Get references
        scope_bool_type = "filter"
        validate = True
        date_range_type = "submittedDate_tdate"
        ref_param = esActions.ref_p_filter(
            i_filter,
            scope_bool_type,
            ext_key,
            entity[key],
            validate,
            date_range_type,
            date_from,
            date_to,
        )

        if i_type == "rsr":
            count = es.count(
                index=f"{struct}-{entity['labHalId']}-researchers-{entity['ldapId']}-documents",
                body=ref_param,
            )["count"]
            references = es.search(
                index=f"{struct}-{entity['labHalId']}-researchers-{entity['ldapId']}-documents",
                body=ref_param,
                size=count,
            )

        elif i_type == "lab":
            count = es.count(
                index=f"{struct}-{entity['halStructId']}-laboratories-documents",
                body=ref_param,
            )["count"]
            references = es.search(
                index=f"{struct}-{entity['halStructId']}-laboratories-documents",
                body=ref_param,
                size=count,
            )
        else:
            return redirect("unknown")

        references_cleaned = []

        for ref in references["hits"]["hits"]:
            references_cleaned.append(ref["_source"])

        return entity, hastoconfirm, references_cleaned


class WordcloudView(CommonContextMixin, TemplateView):
    template_name = "wordcloud.html"

    lang_options = ["ALL", "FR", "EN"]  # langues supportées, créé dynamiquement les onglets
    lang = "ALL"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if "lang" in self.request.GET:
            temp_lang = str(self.request.GET["lang"])
            if temp_lang in self.lang_options:
                langue = temp_lang
            else:
                langue = self.lang
        else:
            langue = self.lang

        entity, hastoconfirm, filtrechercheur, filtrelab, url = self.get_elastic_data(
            context["type"], context["id"], context["struct"]
        )

        context["entity"] = entity
        context["hastoconfirm"] = hastoconfirm
        context["filterRsr"] = filtrechercheur
        context["filterLab"] = filtrelab
        context["url"] = url

        context["lang_options"] = self.lang_options
        context["lang"] = langue

        return context

    def get_elastic_data(self, i_type, p_id, struct):
        # Get scope data
        key, search_id, index_pattern, ext_key, scope_param = get_scope_data(i_type, p_id)

        res = es.search(index=f"{struct}-{search_id}{index_pattern}", body=scope_param)
        # on pointe sur index générique, car pas de LabHalId ?

        try:
            entity = res["hits"]["hits"][0]["_source"]
        except IndexError:
            return redirect("unknown")
        # /

        hastoconfirm = False

        field = "harvested_from_ids"
        validate = False
        if i_type == "rsr":
            hastoconfirm_param = esActions.confirm_p(field, entity["halId_s"], validate)
        elif i_type == "lab":
            hastoconfirm_param = esActions.confirm_p(field, entity["halStructId"], validate)
        else:
            return redirect("unknown")

        if es.count(index=f"{struct}*-documents", body=hastoconfirm_param)["count"] > 0:
            hastoconfirm = True

        # Get first submittedDate_tdate date
        field = "harvested_from_ids"

        if i_type == "rsr":
            indexsearch = f"{struct}-{entity['labHalId']}-researchers-{entity['ldapId']}-documents"
            filtrechercheur = f'_index: "{indexsearch}"'
            filtrelab = ""

        elif i_type == "lab":
            indexsearch = f"{struct}-{entity['halStructId']}-laboratories-documents"
            filtrechercheur = ""
            filtrelab = f'_index: "{indexsearch}"'
        else:
            return redirect("unknown")

        url = (
            viewsActions.vizualisation_url()
        )  # permet d'ajuster l'url des visualisations en fonction du build

        return entity, hastoconfirm, filtrechercheur, filtrelab, url


class IndexView(CommonContextMixin, TemplateView):
    template_name = "index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get parameters
        context["indexcat"] = self.request.GET.get("indexcat")
        context["indexstruct"] = self.request.GET.get("indexstruct")

        entities, struct_tab = self.get_elastic_data(context["indexcat"], context["indexstruct"])

        context["entities"] = entities
        context["struct_tab"] = struct_tab

        if context["type"] == -1 and context["id"] == -1:
            del context["type"]
            del context["id"]
            del context["struct"]

        return context

    def get_elastic_data(self, indexcat, indexstruct):
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

        return cleaned_entities, struct_tab


class FAQView(CommonContextMixin, TemplateView):
    template_name = "faq.html"


class RessourcesView(CommonContextMixin, TemplateView):
    template_name = "ressources.html"


class PresentationView(CommonContextMixin, TemplateView):
    template_name = "presentation.html"


class UnknownView(TemplateView):
    template_name = "404.html"
