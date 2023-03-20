import json
from datetime import datetime

from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.generic import TemplateView
from elasticsearch import BadRequestError
from uniauth.decorators import login_required

from . import forms, viewsActions
from .libs import esActions, halConcepts
from .libs.elastichal import collecte_docs, indexe_chercheur
from .viewsActions import idhal_checkout

es = esActions.es_connector()


class CommonContextMixin:
    """
    Gestion des fonctions communes à l'ensemble des vues d'un profil enregistré.
    Assure la récupération des éléments de contexte communs,
    et du renvoi vers la page après exécution de la fonction.
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

        ldapid = request.GET.get("ldapid")

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


class ElasticContextMixin:
    """
    Gestion des fonctions communes aux vues utilisant elastic
    """

    def get_scope_data(self, i_type, p_id):
        """
        Retourne des valeurs de variable en fonction du profil (chercheur,labo)
        """
        # utiliser cette fonction pour call get_scope_data
        # key, search_id, index_pattern, ext_key, scope_param = get_scope_data(i_type, p_id)

        if i_type == "rsr":
            field = "_id"
            key = "halId_s"
            search_id = "*"
            index_pattern = "-researchers"

        elif i_type == "lab":
            field = "halStructId"
            key = "halStructId"
            search_id = p_id
            index_pattern = "-laboratories"
        else:
            return redirect("unknown")

        ext_key = "harvested_from_ids"

        scope_param = esActions.scope_p(field, p_id)

        return key, search_id, index_pattern, ext_key, scope_param

    def validated_notices_state(self, struct, i_type, entity):
        """
        Check if at least one notice is in the state setup of the "validate" variable.
        If not, a ping gonna appear next to check in the menu.
        """
        hastoconfirm = False

        validate = True
        if i_type == "rsr":
            field = "authIdHal_s"
            hastoconfirm_param = esActions.confirm_p(field, entity["halId_s"], validate)

        elif i_type == "lab":
            field = "labStructId_i"
            hastoconfirm_param = esActions.confirm_p(field, entity["halStructId"], validate)
        else:
            return redirect("unknown")

        if es.count(index=f"{struct}*-documents", body=hastoconfirm_param)["count"] == 0:
            hastoconfirm = True

        return hastoconfirm


class CreateView(TemplateView):
    """
    Gestion de la page "Création de profil"
    """

    template_name = "create.html"
    form_class = forms.CreateCredentials

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["ldapid"] = self.request.GET.get("ldapid")
        context["id_halerror"] = self.request.GET.get("iDhalerror", False)
        context["data"] = "create"
        context["halId_s"] = "nullNone"
        context["idRef"] = "nullNone"
        context["orcId"] = "nullNone"
        context["autres"] = "nullNone"
        context["form"] = self.form_class()
        return context

    def post(self, request, *args, **kwargs):
        form = self.form_class(request.POST)
        if form.is_valid():
            ldapid = self.request.GET.get("ldapid")
            idref = form.cleaned_data["f_IdRef"]
            idhal = form.cleaned_data["f_halId_s"]
            orcid = form.cleaned_data["f_orcId"]
            tempo_lab = form.cleaned_data["f_labo"]
            tempo_lab = tempo_lab.replace("'", "")
            tempo_lab = tempo_lab.replace("(", "")
            tempo_lab = tempo_lab.replace(")", "")
            tempo_lab = tempo_lab.split(",")
            labo = tempo_lab[0].strip()
            accro_lab = tempo_lab[1].strip()

            idhal_test = idhal_checkout(idhal)

            if idhal_test > 0:
                indexe_chercheur(ldapid, accro_lab, labo, idhal, idref, orcid)
                field = "halId_s"
                scope_param = esActions.scope_p(field, idhal)
                count = es.count(index="*-researchers", body=scope_param)["count"]
                res = es.search(index="*-researchers", body=scope_param, size=count)
                entity = res["hits"]["hits"][0]["_source"]
                struct = entity["structSirene"]
                date_to = datetime.today().strftime("%Y-%m-%d")
                return redirect(
                    f"/check/?struct={struct}&type=rsr"
                    + f"&id={ldapid}&orcId={orcid}&from=1990-01-01&to={date_to}&data=credentials"
                )
            else:
                return redirect(
                    f"/create/?ldapid={ldapid}"
                    + "&halId_s=nullNone&orcId=nullNone&idRef=nullNone&iDhalerror=True"
                )

        # form is not valid, render the template again with the errors
        context = self.get_context_data(**kwargs)
        context["form"] = form
        return self.render_to_response(context)


@method_decorator(login_required, name="dispatch")
class CheckView(CommonContextMixin, ElasticContextMixin, TemplateView):
    """
    Gestion de la page gérant "vérification des données"
    """

    template_name = "check.html"

    data_check_options = [
        "credentials",
        "references",
        "expertise",
        "guiding-domains",
        "state",
        "research-description",
    ]
    data_check_default = "credentials"

    def get_xframe_options_value(self):
        return "ALLOW-FROM http://localhost:8000/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if "data" in self.request.GET:
            temp_data = self.request.GET["data"]
            if temp_data in self.data_check_options:
                context["data"] = temp_data
            else:
                context["data"] = self.data_check_default
        else:
            context["data"] = self.data_check_default

        context["entity"] = self.get_entity_data(context["struct"], context["type"], context["id"])

        context["hasToConfirm"] = self.validated_notices_state(
            context["struct"], context["type"], context["entity"]
        )

        if context["data"] == "state":
            researchers = self.get_state_case(context["id"])
            context["researchers"] = researchers

        if context["data"] == "credentials":
            context["form"] = self.get_credential_case(context["type"], context["entity"])

        if context["data"] == "research-description":
            (
                guidingKeywords,
                research_summary,
                research_projects_in_progress,
                research_projects_and_fundings,
                form,
            ) = self.get_rsr_description_case(context["entity"])

            context["guidingKeywords"] = guidingKeywords
            context["research_summary"] = research_summary
            context["research_projects_in_progress"] = research_projects_in_progress
            context["research_projects_and_fundings"] = research_projects_and_fundings
            context["form"] = form

        if context["data"] == "expertise":
            validation, concepts = self.get_expertise_case(context["entity"])
            context["validation"] = validation
            context["concepts"] = concepts

        if context["data"] == "guiding-domains":
            domains, guiding_domains = self.get_guiding_domains_case(context["entity"])
            context["domains"] = domains
            context["guidingDomains"] = guiding_domains

        if context["data"] == "references":
            validation, references = self.get_references_case(
                context["struct"],
                context["type"],
                context["id"],
                context["entity"],
                context["from"],
                context["to"],
            )
            context["validation"] = validation
            context["references"] = references
            if "taches" in self.request.GET:
                context["taches"] = self.request.GET["taches"]

        return context

    def get_entity_data(self, struct, i_type, p_id):
        key, search_id, index_pattern, ext_key, scope_param = self.get_scope_data(i_type, p_id)
        res = es.search(index=f"{struct}-{search_id}{index_pattern}", body=scope_param)

        entity = res["hits"]["hits"][0]["_source"]

        return entity

    def get_state_case(self, p_id):
        field = "labHalId"
        rsr_param = esActions.scope_p(field, p_id)

        count = es.count(index="*-researchers", body=rsr_param)["count"]

        rsrs = es.search(index="*-researchers", body=rsr_param, size=count)

        rsrs_cleaned = []

        for result in rsrs["hits"]["hits"]:
            rsrs_cleaned.append(result["_source"])

        return rsrs_cleaned

    def get_credential_case(self, i_type, entity):
        form = ""
        if i_type == "rsr":
            orcid = ""
            if "orcId" in entity:
                orcid = entity["orcId"]

            rsr_function = 0
            if "function" in entity:
                rsr_function = entity["function"]

            # integration contenus
            # "extIds": ["a", "b", "c"],
            form = forms.ValidCredentials(
                halId_s=entity["halId_s"],
                aurehalId=entity["aurehalId"],
                laboratory=entity["lab"],
                function=rsr_function,
                idRef=entity["idRef"],
                orcId=orcid,
            )

        if i_type == "lab":
            form = forms.ValidLabCredentials(
                halStructId=entity["halStructId"],
                rsnr=entity["rsnr"],
                idRef=entity["idRef"],
            )

        return form

    def get_rsr_description_case(self, entity):
        if "research_summary" not in entity:
            research_summary = ""
        else:
            research_summary = entity["research_summary"]

        if "research_projectsAndFundings" not in entity:
            research_projects_and_fundings = ""
        else:
            research_projects_and_fundings = entity["research_projectsAndFundings"]

        if "research_projectsInProgress" not in entity:
            research_projects_in_progress = ""
        else:
            research_projects_in_progress = entity["research_projectsInProgress"]

        if "guidingKeywords" not in entity:
            guidingKeywords = ""
        else:
            guidingKeywords = ";".join(entity["guidingKeywords"])

        # "extIds": ["a", "b", "c"],
        form = (
            forms.SetResearchDescription(
                guidingKeywords=guidingKeywords,
                research_summary=research_summary,
                research_projectsInProgress=research_projects_in_progress,
                research_projectsAndFundings=research_projects_and_fundings,
            ),
        )

        return (
            guidingKeywords,
            research_summary,
            research_projects_in_progress,
            research_projects_and_fundings,
            form,
        )

    def get_expertise_case(self, entity):
        if "validation" in self.request.GET:
            validation = self.request.GET["validation"]

            if validation == "1":
                validate = "validated"
            elif validation == "0":
                validate = "invalidated"
            else:
                return redirect("unknown")
        else:
            return redirect("unknown")

        concepts = []
        if "children" in entity["concepts"]:
            for children in entity["concepts"]["children"]:
                if "state" in children.keys() and children["state"] == validate:
                    concepts.append(
                        {
                            "id": children["id"],
                            "label_fr": children["label_fr"],
                            "state": validate,
                        }
                    )
                if "children" in children:
                    for children1 in children["children"]:
                        if "state" in children1.keys():
                            if children1["state"] == validate:
                                concepts.append(
                                    {
                                        "id": children1["id"],
                                        "label_fr": "&nbsp;&nbsp;&nbsp;&nbsp;&bull; "
                                        + children1["label_fr"],
                                        "state": validate,
                                    }
                                )
                            else:
                                print(children1)
                        if "children" in children1:
                            for children2 in children1["children"]:
                                if "state" in children2.keys() and children2["state"] == validate:
                                    concepts.append(
                                        {
                                            "id": children2["id"],
                                            "label_fr": "&nbsp;&nbsp;&nbsp;&nbsp;\
                                            &nbsp;&nbsp;&nbsp;&nbsp;- "
                                            + children2["label_fr"],
                                            "state": validate,
                                        }
                                    )
        return validation, concepts

    def get_guiding_domains_case(self, entity):
        domains = halConcepts.concepts()

        guiding_domains = []

        if "guidingDomains" in entity:
            guiding_domains = entity["guidingDomains"]

        return domains, guiding_domains

    def get_references_case(self, struct, i_type, p_id, entity, date_from, date_to):
        if "validation" in self.request.GET:
            validation = self.request.GET["validation"]
            if validation == "1":
                validate = True
            elif validation == "0":
                validate = False
            else:
                return redirect("unknown")
        else:
            return redirect("unknown")

        key, search_id, index_pattern, ext_key, scope_param = self.get_scope_data(i_type, p_id)

        date_range_type = "submittedDate_tdate"
        scope_bool_type = "must"
        ref_param = esActions.ref_p(
            scope_bool_type,
            ext_key,
            entity[key],
            validate,
            date_range_type,
            date_from,
            date_to,
        )
        # print(ref_param)

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
        # /
        return validation, references_cleaned

    def post(self, request, *args, **kwargs):
        if "update_reference" in request.POST:
            struct = request.POST.get("struct")
            i_type = request.POST.get("type")
            p_id = request.POST.get("id")
            taches = self.update_references(struct, i_type, p_id)
            response_data = {"task_id": taches}
            print(response_data)
            response = JsonResponse(response_data)
            response["X-Frame-Options"] = self.get_xframe_options_value()
            return response

    def update_references(self, struct, i_type, p_id):
        if i_type == "rsr":
            scope_param = esActions.scope_p("_id", p_id)

            res = es.search(index=f"{struct}*-researchers", body=scope_param)
            try:
                entity = res["hits"]["hits"][0]["_source"]
            except IndexError:
                return redirect("unknown")

            result = collecte_docs.delay(entity, True)
            taches = result.task_id
            return taches
        else:
            return ""


class DashboardView(CommonContextMixin, ElasticContextMixin, TemplateView):
    """
    Gestion de la page affichant les tableaux de bord sous Kibana
    """

    template_name = "dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        (
            entity,
            filtrechercheur,
            filtre_lab_a,
            filtre_lab_b,
            url,
            dash,
        ) = self.get_elastic_data(context["type"], context["id"], context["struct"])

        context["dash"] = dash
        context["entity"] = entity
        context["filterRsr"] = filtrechercheur
        context["filterlabA"] = filtre_lab_a
        context["filterlabB"] = filtre_lab_b
        context["url"] = url

        return context

    def get_elastic_data(self, i_type, p_id, struct):
        # Get scope data
        key, search_id, index_pattern, ext_key, scope_param = self.get_scope_data(i_type, p_id)

        res = es.search(index=f"{struct}-{search_id}{index_pattern}", body=scope_param)
        # on pointe sur index générique, car pas de LabHalId ?
        try:
            entity = res["hits"]["hits"][0]["_source"]
        except (IndexError, BadRequestError):
            return redirect("unknown")
        # /

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

        return entity, filtrechercheur, filtre_lab_a, filtre_lab_b, url, dash


class ReferencesView(CommonContextMixin, ElasticContextMixin, TemplateView):
    """
    Gestion de la page affichant les références du profil sélectionné
    """

    template_name = "references.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if "filter" in self.request.GET:
            context["filter"] = self.request.GET["filter"]
        else:
            context["filter"] = -1

        entity, references_cleaned = self.get_elastic_data(
            context["type"],
            context["id"],
            context["struct"],
            context["filter"],
            context["from"],
            context["to"],
        )

        context["entity"] = entity
        context["references"] = references_cleaned
        return context

    def get_elastic_data(self, i_type, p_id, struct, i_filter, date_from, date_to):
        # Get scope data
        key, search_id, index_pattern, ext_key, scope_param = self.get_scope_data(i_type, p_id)
        res = es.search(index=f"{struct}-{search_id}{index_pattern}", body=scope_param)

        try:
            entity = res["hits"]["hits"][0]["_source"]
        except IndexError:
            return redirect("unknown")

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

        return entity, references_cleaned


@method_decorator(xframe_options_exempt, name="dispatch")
class TerminologyView(CommonContextMixin, ElasticContextMixin, TemplateView):
    """
    Gestion de la page affichant les domaines d'expertise du profil sélectionné
    """

    template_name = "terminology.html"

    def get_template_names(self):
        # Override initial template name if the page is called by the iframe link from outside.
        template_names = [self.template_name]

        if self.request.GET.get("export") == "True":
            template_names.insert(0, "terminology_ext.html")

        return template_names

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        entity = self.get_elastic_data(context["type"], context["id"], context["struct"])

        context["entity"] = entity

        return context

    def get_elastic_data(self, i_type, p_id, struct):
        # Get scope data
        key, search_id, index_pattern, ext_key, scope_param = self.get_scope_data(i_type, p_id)

        res = es.search(index=f"{struct}-{search_id}{index_pattern}", body=scope_param)
        # on pointe sur index générique, car pas de LabHalId ?
        try:
            entity = res["hits"]["hits"][0]["_source"]
        except IndexError:
            return redirect("unknown")
        # /

        if i_type == "lab":
            entity["concepts"] = json.dumps(entity["concepts"])

        if i_type == "rsr":
            entity["concepts"] = json.dumps(entity["concepts"])

        entity["concepts"] = json.loads(entity["concepts"])

        if i_type == "rsr" and "children" in entity["concepts"]:
            for children in list(entity["concepts"]["children"]):
                if children["state"] == "invalidated":
                    entity["concepts"]["children"].remove(children)

                if "children" in children:
                    for children1 in list(children["children"]):
                        if children1["state"] == "invalidated":
                            children["children"].remove(children1)

                        if "children" in children1:
                            for children2 in list(children1["children"]):
                                if children2["state"] == "invalidated":
                                    children1["children"].remove(children2)

        if i_type == "lab" and "children" in entity["concepts"]:
            for children in list(entity["concepts"]["children"]):
                state = "invalidated"
                if "researchers" in children:
                    for rsr in children["researchers"]:
                        if rsr["state"] == "validated":
                            state = "validated"
                    if state == "invalidated":
                        entity["concepts"]["children"].remove(children)

                if "children" in children:
                    for children1 in list(children["children"]):
                        state = "invalidated"
                        if "researchers" in children1:
                            for rsr in children1["researchers"]:
                                if rsr["state"] == "validated":
                                    state = "validated"
                            if state == "invalidated":
                                children["children"].remove(children1)

                        if "children" in children1:
                            for children2 in list(children1["children"]):
                                state = "invalidated"
                                if "researchers" in children2:
                                    for rsr in children2["researchers"]:
                                        if rsr["state"] == "validated":
                                            state = "validated"
                                    if state == "invalidated":
                                        children1["children"].remove(children2)
        return entity


class LexiconView(CommonContextMixin, ElasticContextMixin, TemplateView):
    """
    Gestion de la page "lexiques extraits"
    """

    template_name = "lexicon.html"

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

        entity, filtrechercheur, filtrelab, url = self.get_elastic_data(
            context["type"], context["id"], context["struct"]
        )

        context["entity"] = entity
        context["filterRsr"] = filtrechercheur
        context["filterLab"] = filtrelab
        context["url"] = url

        context["lang_options"] = self.lang_options
        context["lang"] = langue

        return context

    def get_elastic_data(self, i_type, p_id, struct):
        # Get scope data
        key, search_id, index_pattern, ext_key, scope_param = self.get_scope_data(i_type, p_id)

        res = es.search(index=f"{struct}-{search_id}{index_pattern}", body=scope_param)

        try:
            entity = res["hits"]["hits"][0]["_source"]
        except IndexError:
            return redirect("unknown")
        # /
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

        return entity, filtrechercheur, filtrelab, url


@method_decorator(login_required, name="dispatch")
class ToolsView(CommonContextMixin, ElasticContextMixin, TemplateView):
    """
    Gestion de la page "Outils", proposant des fonctionnalités pour les profils laboratoires.
    (Export HCERES, Cohésion des données)
    """

    template_name = "tools.html"

    data_tools_options = ["hceres", "consistency"]
    data_tool_default = "hceres"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if "data" in self.request.GET:
            temp_data = self.request.GET["data"]
            if temp_data in self.data_tools_options:
                context["data"] = temp_data
            else:
                context["data"] = self.data_tool_default
        else:
            context["data"] = self.data_tool_default

        context["entity"] = self.get_entity_data(context["struct"], context["type"], context["id"])

        if context["data"] == "consistency":
            context["consistency"] = self.get_consistency_data(
                context["id"], context["from"], context["to"]
            )

        return context

    def get_consistency_data(self, p_id, date_from, date_to):
        # parametres fixes pour la recherche dans les bases Elastic
        scope_bool_type = "filter"
        scope_field = "harvested_from_ids"
        validate = True
        date_range_type = "submittedDate_tdate"

        # récupere les infos sur les chercheurs attachés au laboratoire
        field = "labHalId"
        rsr_param = esActions.scope_p(field, p_id)

        count = es.count(index="*-researchers", body=rsr_param)["count"]

        rsrs = es.search(index="*-researchers", body=rsr_param, size=count)
        rsrs_cleaned = []

        for result in rsrs["hits"]["hits"]:
            rsrs_cleaned.append(result["_source"])

        consistencyvalues = []

        for x in range(len(rsrs_cleaned)):
            ldapid = rsrs_cleaned[x]["ldapId"]
            hal_id_s = rsrs_cleaned[x]["halId_s"]
            struct = rsrs_cleaned[x]["structSirene"]
            name = rsrs_cleaned[x]["name"]
            validated = rsrs_cleaned[x]["validated"]

            # nombre de documents de l'auteur coté lab
            ref_lab = esActions.ref_p(
                scope_bool_type,
                "authIdHal_s",
                hal_id_s,
                validate,
                date_range_type,
                date_from,
                date_to,
            )
            raw_lab_doc_count = es.count(
                index=f"{struct}-{p_id}-laboratories-documents", body=ref_lab
            )["count"]

            # nombre de documents de l'auteur dans son index
            ref_param = esActions.ref_p(
                scope_bool_type,
                scope_field,
                hal_id_s,
                validate,
                date_range_type,
                date_from,
                date_to,
            )
            raw_searcher_doc_count = es.count(
                index=f"{struct}-{p_id}-researchers-{ldapid}-documents", body=ref_param
            )["count"]

            # création du dict à rajouter dans la liste
            profiledict = {
                "name": name,
                "ldapId": ldapid,
                "validated": validated,
                "labcount": raw_lab_doc_count,
                "searchercount": raw_searcher_doc_count,
            }

            # rajout à la liste
            consistencyvalues.append(profiledict)

            return consistencyvalues

    def get_entity_data(self, struct, i_type, p_id):
        key, search_id, index_pattern, ext_key, scope_param = self.get_scope_data(i_type, p_id)
        res = es.search(index=f"{struct}-{search_id}{index_pattern}", body=scope_param)

        entity = res["hits"]["hits"][0]["_source"]

        return entity


class IndexView(CommonContextMixin, TemplateView):
    """
    Gestion des pages d'indexation des profils chercheurs et laboratoires
    """

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


class SearchView(CommonContextMixin, TemplateView):
    """
    Gestion de la page de recherche à partir de mots clés
    """

    template_name = "search2.html"


class FAQView(CommonContextMixin, TemplateView):
    """
    Gestion de la page des questions fréquentes
    """

    template_name = "faq.html"


class RessourcesView(CommonContextMixin, TemplateView):
    """
    Gestion de la page des ressources à destination des chercheurs
    """

    template_name = "ressources.html"


class PresentationView(CommonContextMixin, TemplateView):
    """
    Gestion de la page de présentation du projet
    """

    template_name = "presentation.html"


class UnknownView(TemplateView):
    """
    Gestion de l'affichage de la page d'erreur si l'url est inconnue
    """

    template_name = "404.html"
