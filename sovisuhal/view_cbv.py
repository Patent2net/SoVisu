import json
from datetime import datetime

from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.generic import TemplateView
from elasticsearch import BadRequestError
from uniauth.decorators import login_required

from constants import SV_INDEX, SV_STRUCTURES_REFERENCES, SV_LAB_INDEX, TIMEZONE, KIBANA_URL
from . import forms, viewsActions
from .libs import esActions, halConcepts
from .libs.elastichal import collecte_docs, indexe_chercheur
from .viewsActions import idhal_checkout

es = esActions.es_connector()


# TODO: Faire un fichier pour les Mixin
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
        if "type" in request.GET:
            i_type = request.GET["type"]
        else:
            i_type = -1

        if "id" in request.GET:
            p_id = request.GET["id"]
        else:
            p_id = -1

        ldapid = request.GET.get("ldapid")

        return i_type, p_id, ldapid

    def get_date(self, request):
        start_date = "2000"

        if "from" in request.GET:
            date_from = request.GET["from"]
        else:
            date_from = f"{start_date[0:4]}-01-01"

        if "to" in request.GET:
            date_to = request.GET["to"]
        else:
            date_to = datetime.now(tz=TIMEZONE).date().isoformat()

        return date_from, date_to

    def validated_notices_state(self, i_type, p_id):  # TODO: Revoir la fonction
        """
        Check if at least one notice is in the state setup of the "validate" variable.
        If not, a ping gonna appear next to check in the menu.
        """
        hastoconfirm = False

        validate = True
        if i_type == "rsr":
            index = SV_INDEX
            field = "authIdHal_s"
            hastoconfirm_param = esActions.confirm_p(field, p_id, validate)

        elif i_type == "lab":
            index = SV_LAB_INDEX
            field = "labStructId_i"
            hastoconfirm_param = esActions.confirm_p(field, p_id, validate)
        else:
            return redirect("unknown")

        if es.count(index=index, query=hastoconfirm_param)["count"] == 0:
            hastoconfirm = True

        return hastoconfirm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        (
            context["type"],
            context["id"],
            context["ldapid"],
        ) = self.get_regular_parameters(self.request)
        context["from"], context["to"] = self.get_date(self.request)
        context["hasToConfirm"] = self.validated_notices_state(context["type"], context["id"])
        return context


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
            structid = form.cleaned_data["f_inst"]
            labHalId = form.cleaned_data["f_labo"]
            print(labHalId)

            idhal_test = idhal_checkout(idhal)

            if idhal_test > 0:
                labo_data = es.get(index=SV_STRUCTURES_REFERENCES, id=labHalId)
                labo_data = labo_data["_source"]
                indexe_chercheur(
                    structid, ldapid, labo_data["acronym_s"], labHalId, idhal, idref, orcid
                )
                entity = es.get(index=SV_INDEX, id=idhal)
                entity = entity["_source"]
                user_token = entity["halId_s"]
                date_to = datetime.now(tz=TIMEZONE).date().isoformat()
                return redirect(
                    f"/check/?type=rsr"
                    + f"&id={user_token}&from=1990-01-01&to={date_to}&data=credentials"
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
class CheckView(CommonContextMixin, TemplateView):
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
        "affiliations",
    ]
    data_check_default = "credentials"

    def countPoint(self):
        return self.chemin.count(".")

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

        context["entity"] = self.get_entity_data(context["type"], context["id"])

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

        if context["data"] == "expertise":  # TODO: Doit fonctionner avec test_expertises
            validation, expertises = self.get_expertise_case(context["id"])
            context["validation"] = validation
            context["expertises"] = expertises

        if context["data"] == "guiding-domains":
            domains, guiding_domains = self.get_guiding_domains_case(context["entity"], context["type"])
            context["domains"] = domains
            context["guidingDomains"] = guiding_domains
            # TODO: Trouver une alternative à aurehalId si usage structures
            context["aurehal"] = context["entity"][
                "aurehalId"
            ]  # pas sûr que ce soit pas un hack pas bô

        if context["data"] == "references":
            validation, references = self.get_references_case(
                context["type"],
                context["id"],
                context["from"],
                context["to"],
            )
            context["validation"] = validation
            context["references"] = references
            if "taches" in self.request.GET:
                context["taches"] = self.request.GET["taches"]

        if context["data"] == "affiliations":
            structurelist = self.get_affiliations_case(context["id"], context["type"])
            context["structurelist"] = structurelist

            non_affiliated_structures = self.get_non_affiliated_structures(context["id"], context["type"])
            context["non_affiliated_structures"] = json.dumps(
                [
                    {"id": structure["docid"], "label": structure["label_s"]}
                    for structure in non_affiliated_structures
                ]
            )

        return context

    def get_entity_data(self, i_type, p_id):

        if i_type == "lab":
            indexsearch = SV_LAB_INDEX
        elif i_type == "rsr":
            indexsearch = SV_INDEX
        else:
            return redirect("unknown")

        res = es.get(index=indexsearch, id=p_id)
        # on pointe sur index générique, car pas de LabHalId ?
        try:
            entity = res["_source"]
        except (IndexError, BadRequestError):
            return redirect("unknown")

        return entity

    def get_state_case(self, p_id):
        field = "labHalId"
        rsr_param = esActions.scope_p(field, p_id)

        count = es.count(index="test_researchers", query=rsr_param)["count"]

        rsrs = es.search(index="test_researchers", query=rsr_param, size=count)

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
                halStructId=entity["docid"],
                rsnr=entity.get("rnsr_s"),
                idRef=entity.get("idref_s"),
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

    def get_expertise_case(self, p_id):
        # TODO: In the related html, find a way to order taking account of "chemin" field

        # Peut être un sort() puis un count (".") dans chemin qui détermine le nombre de tabulations ;-)
        expertise_cleaned = []

        validation = self.request.GET.get("validation")
        query = {
            "bool": {
                "must": [
                    {"match": {"sovisu_category": "expertise"}},
                    {"match": {"idhal": p_id}},
                ]
            }
        }
        expertises_count = es.count(index=SV_INDEX, query=query)["count"]
        searcher_expertises = es.search(index=SV_INDEX, query=query, size=expertises_count)
        searcher_expertises = searcher_expertises["hits"]["hits"]

        if validation == "1":  # show the expertises validated by searcher
            for expertise in searcher_expertises:
                if expertise["_source"]["validated"]:
                    expertise_cleaned.append(expertise["_source"])

        elif validation == "0":  # show the expertises invalidated by searcher
            for expertise in searcher_expertises:
                if not expertise["_source"]["validated"]:
                    expertise_cleaned.append(expertise["_source"])
        else:
            return redirect("unknown")
        # print(expertise_cleaned)

        return validation, sorted(expertise_cleaned, key=lambda x: x["chemin"])

    def get_guiding_domains_case(self, entity, i_type):
        domains = halConcepts.concepts()
        query = {
            "bool": {
                "must": [
                    {"match": {"sovisu_category": "expertise"}},
                    {"match": {"validated": True}},
                ]
            }
        }

        if i_type == 'rsr':
            query["bool"]["must"].append({"match": {"idhal": entity["idhal"]}})
        if i_type == 'lab':
            query["bool"]["must"].append({"match": {"idhal": entity["docid"]}})

        expertises_count = es.count(index=SV_INDEX, query=query)["count"]
        searcher_expertises = es.search(index=SV_INDEX, query=query, size=expertises_count)
        searcher_expertises = [
            exp["_source"]["chemin"].replace("domAurehal.", "")
            for exp in searcher_expertises["hits"]["hits"]
        ]

        guiding_domains = searcher_expertises
        if "guidingDomains" in entity:
            guiding_domains = entity["guidingDomains"]

        return domains, guiding_domains

    def get_references_case(self, i_type, p_id, date_from, date_to):
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

        date_range_type = "submittedDate_tdate"

        # remplace ref_p
        query = {
            "bool": {
                "must": [
                    {"match": {"sovisu_category": "notice"}},
                    {"match": {"sovisu_id": f"{p_id}.*"}},
                    {"match": {"sovisu_validated": validate}},
                    {"range": {date_range_type: {"gte": date_from, "lte": date_to}}},
                ]
            }
        }

        if i_type == "rsr":
            index = SV_INDEX
        elif i_type == "lab":  # TODO: séparer RSR et LAB
            index = SV_LAB_INDEX
        else:
            return redirect("unknown")

        count = es.count(index=index, query=query)["count"]

        references = es.search(index=index, query=query, size=count)

        references_cleaned = []

        for ref in references["hits"]["hits"]:
            references_cleaned.append(ref["_source"])
        # /
        return validation, references_cleaned

    def get_affiliations_case(self, p_id, i_type):

        if i_type == "rsr":
            index = SV_INDEX
            key = "sv_affiliation"
        elif i_type == "lab":
            index = SV_LAB_INDEX
            key = "parentDocid_i"
        else:
            return redirect("unknown")

        content = es.get(index=index, id=p_id)
        content = content["_source"]
        affiliates = content[key]

        affiliates_detail = []
        for affiliate in affiliates:
            affiliate_exist = es.exists(index=SV_STRUCTURES_REFERENCES, id=affiliate)
            if affiliate_exist:
                affiliates_content = es.get(index=SV_STRUCTURES_REFERENCES, id=affiliate)
                affiliates_content = affiliates_content["_source"]
                affiliates_detail.append(affiliates_content)

        return affiliates_detail

    def get_non_affiliated_structures(self, p_id, i_type):
        # Fetch all available structures
        all_structures = es.search(
            index=SV_STRUCTURES_REFERENCES,
            body={"query": {"match_all": {}}},
            size=200,  # set the number of structures to fetch
        )
        all_structures_list = [record["_source"] for record in all_structures["hits"]["hits"]]
        # Fetch already affiliated structures
        affiliated_structures = self.get_affiliations_case(p_id, i_type)

        # Create a set of affiliated structure ids
        affiliated_structure_ids = set(structure["docid"] for structure in affiliated_structures)

        # Filter to get non-affiliated structures
        non_affiliated_structures = [
            structure
            for structure in all_structures_list
            if structure["docid"] not in affiliated_structure_ids
        ]
        return non_affiliated_structures

    def post(self, request, *args, **kwargs):
        if "update_reference" in request.POST:
            i_type = request.POST.get("type")
            p_id = request.POST.get("id")
            taches = self.update_references(i_type, p_id)
            response_data = {"task_id": taches}
            response = JsonResponse(response_data)
            response["X-Frame-Options"] = self.get_xframe_options_value()
            return response

        if "add_affiliation" in request.POST:
            print("add affiliation sent")
            p_id = request.POST.get("entity_id")
            affiliate_id = request.POST.get("docid")
            response = self.add_affiliation(p_id, affiliate_id)
            print(f"user id: {p_id}, affiliate_id: {affiliate_id}")
            return JsonResponse({"status": response})

        if "remove_affiliation" in request.POST:
            p_id = request.POST.get("entity_id")
            affiliate_id = request.POST.get("docid")
            response = self.remove_affiliation(p_id, affiliate_id)
            return JsonResponse({"status": response})

    def update_references(self, i_type, p_id):
        if i_type == "rsr":
            print("type rsr")
            res = es.get(index=SV_INDEX, id=p_id)
            try:
                entity = res["_source"]
            except IndexError:
                return redirect("unknown")

            result = collecte_docs.delay(entity)
            taches = result.task_id
            return taches

        if i_type == "lab":
            print("type lab")

            res = es.get(index=SV_LAB_INDEX, id=p_id)
            try:
                entity = res["_source"]
            except IndexError:
                return redirect("unknown")

            result = collecte_docs.delay(entity)
            taches = result.task_id
            return taches

        else:
            return ""

    def add_affiliation(self, p_id, affiliate_id):
        chercheur = es.get(index=SV_INDEX, id=p_id)
        chercheur_affiliations = chercheur["_source"]["sv_affiliation"]

        if affiliate_id not in chercheur_affiliations:
            chercheur_affiliations.append(affiliate_id)
        else:
            return "value already exist"

        doc = {"sv_affiliation": chercheur_affiliations}
        es.update(index=SV_INDEX, id=p_id, doc=doc)

        return "success"

    def remove_affiliation(self, p_id, affiliate_id):
        chercheur = es.get(index=SV_INDEX, id=p_id)
        chercheur_affiliations = chercheur["_source"]["sv_affiliation"]
        print(f"affiliate to remove: {affiliate_id}")
        print(f"chercheur_affiliations: {chercheur_affiliations}")
        affiliate_id = int(affiliate_id)  # TODO: TEMPORARY.
        # Need to declare sv_affiliations as string in elastic mapping
        chercheur_affiliations.remove(affiliate_id)
        print(f"updated chercheur_affiliations: {chercheur_affiliations}")
        doc = {"sv_affiliation": chercheur_affiliations}
        es.update(index=SV_INDEX, id=p_id, doc=doc)
        return "success"


class DashboardView(CommonContextMixin, TemplateView):
    """
    Gestion de la page affichant les tableaux de bord sous Kibana
    """

    # TODO: Changer le dashboard affiché pour la visualisation à partir du nouveau système
    template_name = "dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        (
            entity,
            filtre_idhal,
            filtre_affiliation,
            url,
            dash,
        ) = self.get_elastic_data(context["type"], context["id"])

        context["dash"] = dash
        context["entity"] = entity
        context["filter_idhal"] = filtre_idhal
        context["filter_affiliation"] = filtre_affiliation
        context["url"] = url

        return context

    def get_elastic_data(self, i_type, p_id):

        dash = ""
        filtre_idhal = f'idhal.keyword: "{p_id}"'
        filtre_affiliation = f'sv_affiliation: "{p_id}"'

        if i_type == "rsr":
            indexsearch = SV_INDEX
        elif i_type == "lab":
            indexsearch = SV_LAB_INDEX
            if "dash" in self.request.GET:
                dash = self.request.GET["dash"]
            else:
                dash = "membres"
        else:
            return redirect("unknown")

        res = es.get(index=indexsearch, id=p_id)
        # on pointe sur index générique, car pas de LabHalId ?
        try:
            entity = res["_source"]
        except (IndexError, BadRequestError):
            return redirect("unknown")
        # /

        url = KIBANA_URL

        return entity, filtre_idhal, filtre_affiliation, url, dash


class ReferencesView(CommonContextMixin, TemplateView):
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

        references_cleaned = self.get_elastic_data(
            context["type"],
            context["id"],
            context["filter"],
            context["from"],
            context["to"],
        )

        context["references"] = references_cleaned
        return context

    def get_elastic_data(self, i_type, p_id, i_filter, date_from, date_to):

        # Get references
        validate = True
        ref_param = esActions.ref_p_filter(
            i_filter,
            p_id,
            validate,
            date_from,
            date_to,
        )
        if i_type == "rsr":
            indextype = SV_INDEX
        elif i_type == "lab":
            indextype = SV_LAB_INDEX
        else:
            return redirect("unknown")

        count = es.count(index=indextype, query=ref_param)["count"]
        references = es.search(index=indextype, query=ref_param, size=count)

        references_cleaned = []

        for ref in references["hits"]["hits"]:
            references_cleaned.append(ref["_source"])

        return references_cleaned


@method_decorator(xframe_options_exempt, name="dispatch")
class TerminologyView(CommonContextMixin, TemplateView):
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

        entity = self.get_elastic_data(context["type"], context["id"])

        context["entity"] = entity

        return context

    def get_elastic_data(self, i_type, p_id):
        entity = []
        if i_type == "lab":
            index_pattern = SV_LAB_INDEX
        elif i_type == "rsr":
            index_pattern = SV_INDEX
        else:
            return redirect("unknown")

        query = {
            "bool": {
                "must": [
                    {"match": {"sovisu_category": "expertise"}},
                    {"match": {"idhal": p_id}},
                ]
            }
        }
        expertise_count = es.count(index=index_pattern, query=query)["count"]
        searcher_expertises = es.search(index=index_pattern, query=query, size=expertise_count)[
            "hits"
        ]["hits"]
        # on pointe sur index générique, car pas de LabHalId ?
        for expertise in searcher_expertises:
            entity.append(expertise["_source"])

        # TODO: Find a way to order with expertise["chemin"]
        # try:
        #     entity = res["hits"]["hits"][0]["_source"]
        # except IndexError:
        #     return redirect("unknown")
        # # /
        #
        # if i_type == "lab" or i_type == "rsr":
        #     entity["concepts"] = json.dumps(entity["concepts"])
        #
        # entity["concepts"] = json.loads(entity["concepts"])
        #
        # if i_type == "rsr" and "children" in entity["concepts"]:
        #     for children in list(entity["concepts"]["children"]):
        #         if children["state"] == "invalidated":
        #             entity["concepts"]["children"].remove(children)
        #
        #         if "children" in children:
        #             for children1 in list(children["children"]):
        #                 if children1["state"] == "invalidated":
        #                     children["children"].remove(children1)
        #
        #                 if "children" in children1:
        #                     for children2 in list(children1["children"]):
        #                         if children2["state"] == "invalidated":
        #                             children1["children"].remove(children2)
        #
        # if i_type == "lab" and "children" in entity["concepts"]:
        #     for children in list(entity["concepts"]["children"]):
        #         state = "invalidated"
        #         if "researchers" in children:
        #             for rsr in children["researchers"]:
        #                 if rsr["state"] == "validated":
        #                     state = "validated"
        #             if state == "invalidated":
        #                 entity["concepts"]["children"].remove(children)
        #
        #         if "children" in children:
        #             for children1 in list(children["children"]):
        #                 state = "invalidated"
        #                 if "researchers" in children1:
        #                     for rsr in children1["researchers"]:
        #                         if rsr["state"] == "validated":
        #                             state = "validated"
        #                     if state == "invalidated":
        #                         children["children"].remove(children1)
        #
        #                 if "children" in children1:
        #                     for children2 in list(children1["children"]):
        #                         state = "invalidated"
        #                         if "researchers" in children2:
        #                             for rsr in children2["researchers"]:
        #                                 if rsr["state"] == "validated":
        #                                     state = "validated"
        #                             if state == "invalidated":
        #                                 children1["children"].remove(children2)
        return entity


class LexiconView(CommonContextMixin, TemplateView):
    """
    Gestion de la page "lexiques extraits"
    """

    # TODO: Revoir le filtre pour qu'il affiche les documents liés au chercheur/labo
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

        filtrechercheur, filtrelab, url = self.get_elastic_data(
            context["type"])

        context["filterRsr"] = filtrechercheur
        context["filterLab"] = filtrelab
        context["url"] = url

        context["lang_options"] = self.lang_options
        context["lang"] = langue

        return context

    def get_elastic_data(self, i_type):
        # /
        if i_type == "rsr":
            indexsearch = SV_INDEX
        elif i_type == "lab":
            indexsearch = SV_LAB_INDEX
        else:
            return redirect("unknown")

        filtrechercheur = f'_index: "{indexsearch}"'
        filtrelab = f'_index: "{indexsearch}"'

        url = KIBANA_URL

        return filtrechercheur, filtrelab, url


@method_decorator(login_required, name="dispatch")
class ToolsView(CommonContextMixin, TemplateView):
    """
    Gestion de la page "Outils", proposant des fonctionnalités pour les profils laboratoires.
    (Export HCERES, Cohésion des données)
    """

    # TODO: A revoir lorsque la partie chercheur est réglée.
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

        context["entity"] = self.get_entity_data(context["id"])

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

        count = es.count(index="test_researchers", query=rsr_param)["count"]

        rsrs = es.search(index="test_researchers", query=rsr_param, size=count)
        rsrs_cleaned = []

        for result in rsrs["hits"]["hits"]:
            rsrs_cleaned.append(result["_source"])

        consistencyvalues = []

        for x in range(len(rsrs_cleaned)):
            ldapid = rsrs_cleaned[x]["ldapId"]
            hal_id_s = rsrs_cleaned[x]["halId_s"]
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
            raw_lab_doc_count = es.count(index="test_publications", query=ref_lab)["count"]

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
            raw_searcher_doc_count = es.count(index="test_publications", query=ref_param)["count"]

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

    def get_entity_data(self, p_id):
        res = es.get(index=SV_LAB_INDEX, id=p_id)
        entity = res["_source"]
        return entity


class StructuresIndexView(CommonContextMixin, TemplateView):
    """
    Gestion des pages d'indexation des profils chercheurs et laboratoires
    """

    template_name = "structures_index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get parameters
        context["indexcat"] = self.request.GET.get("indexcat")
        context["indexcategory"] = self.request.GET.get("indexcategory")

        entities, struct_tab = self.get_elastic_data(context["indexcategory"])

        context["entities"] = entities
        context["struct_tab"] = struct_tab

        if context["type"] == -1 and context["id"] == -1:
            del context["type"]
            del context["id"]

        return context

    def get_elastic_data(self, index_category):
        struct_tab = self.get_struct_category()

        indextype = SV_LAB_INDEX
        category_type = index_category
        cleaned_entities = self.get_struct_list(indextype, category_type)

        return cleaned_entities, struct_tab

    def get_struct_category(self):
        """
        This method is used to retrieve the unique categories of structures
        from the SV_LAB_INDEX in Elasticsearch.

        Parameters:
            None

        Returns:
            unique_categories (list): A list containing the unique categories of structures.

        Example Usage:
            unique_categories = StructuresIndexView().get_struct_category()
        """
        body = {
            "size": 0,
            "query": {
                "match": {
                    "sv_parent_type": "structure"
                }
            },
            "aggs": {"unique_categories": {"terms": {"field": "sovisu_category.keyword"}}},
        }

        response = es.search(index=SV_LAB_INDEX, body=body)

        # Get the unique categories from the response
        unique_categories = [
            bucket["key"] for bucket in response["aggregations"]["unique_categories"]["buckets"]
        ]

        return unique_categories

    def get_struct_list(self, indextype, category_type):
        query = {
            "bool": {
                "must": [
                    {"match": {"sovisu_category": category_type}},
                    {"match": {"sv_parent_type": "structure"}},
                ]
            }
        }
        count = es.count(index=f"{indextype}")["count"]
        res = es.search(index=f"{indextype}", query=query, size=count)
        struct_list = [hit["_source"] for hit in res["hits"]["hits"]]

        struct_list = sorted(struct_list, key=lambda k: k["acronym_s"])

        return struct_list


class SearchersIndexView(CommonContextMixin, TemplateView):
    """
    Gestion des pages d'indexation des profils chercheurs et laboratoires
    """

    template_name = "searchers_index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get parameters
        context["indexcat"] = self.request.GET.get("indexcat")
        context["indexstruct"] = self.request.GET.get("indexstruct")

        entities, struct_tab = self.get_elastic_data(context["indexstruct"])

        context["entities"] = entities
        context["struct_tab"] = struct_tab

        if context["type"] == -1 and context["id"] == -1:
            del context["type"]
            del context["id"]

        return context

    def get_elastic_data(self, sv_affiliation):
        structure_type = "laboratory"
        struct_tab = self.get_structure_type_list(structure_type)

        cleaned_entities = self.get_searcher_list(sv_affiliation)

        return cleaned_entities, struct_tab

    def get_structure_type_list(self, type):
        """
        Method: get_structure_type_list(type)

        This method retrieves a list of structure based on the specified type.

        Parameters:
        - type (str): The type of structure to retrieve.

        Returns:
        - struct_tab (list): A list of structures that match the specified type.
        """
        get_institution_query = {
            "bool": {
                "must": [
                    {"match": {"sovisu_category": type}},
                    {"match": {"sv_parent_type": "structure"}},
                ]
            }
        }
        # création dynamique des tabs sur la page à partir de struct_tab
        count = es.count(
            index=SV_LAB_INDEX,
            query=get_institution_query,
        )["count"]
        struct_tab = es.search(
            index=SV_LAB_INDEX, query=get_institution_query, size=count
        )
        struct_tab = [hit["_source"] for hit in struct_tab["hits"]["hits"]]
        return struct_tab

    def get_searcher_list(self, sv_affiliation):
        """
            Fetches a list of searchers sorted by their last name from ElasticSearch,
             based on the provided affiliation value.
 
            Parameters
            ----------
            sv_affiliation : str
                The affiliation value used to filter the search results from the ElasticSearch
                Index.
                It uses 'match' (in ElasticSearch terms) to filter results where 'sv_affiliation'
                 is equal to provided value. If the value is '*', it will take all affiliations.
 
            Returns
            -------
            list
                List of searchers as a dictionary including their details.
                Each 'hit' from ElasticSearch results is extracted as a dictionary using
                 its '_source' attribute.
                The list is sorted by the 'lastName' key of these dictionaries, in ascending order.
        """
        category_type = "searcher"
        query = {
            "bool": {
                "must": [
                    {"match": {"sovisu_category": category_type}},
                    {"match": {"sv_parent_type": "searcher"}},
                ]
            }
        }
        if sv_affiliation != "*":
            query["bool"]["must"].append({"term": {"sv_affiliation": sv_affiliation}})

        indextype = SV_INDEX
        count = es.count(index=f"{indextype}")["count"]
        res = es.search(index=f"{indextype}", query=query, size=count)
        searcher_list = [hit["_source"] for hit in res["hits"]["hits"]]

        searcher_list = sorted(searcher_list, key=lambda k: k["lastName"])

        return searcher_list


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
