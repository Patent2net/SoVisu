import json
from datetime import datetime
import time
from django.contrib import messages
from django.shortcuts import render, redirect
from django.views.decorators.clickjacking import xframe_options_exempt
from . import forms, viewsActions

from urllib.parse import urlencode
from django.urls import reverse

from .libs import halConcepts, esActions


# Connect to DB
es = esActions.es_connector()


# /Pages
def unknown(request):
    """
    Gestion de l'affichage de la page d'erreur si l'url est inconnue
    """
    return render(request, "404.html")


def create(request):
    """
    Gestion de la page affichant le formulaire de création d'un nouveau profil à un utilisateur non reconnu
    """
    ldapid = request.GET["ldapid"]  # ldapid
    id_halerror = False
    if "iDhalerror" in request.GET:
        id_halerror = request.GET["iDhalerror"]

    return render(
        request,
        "create.html",
        {
            "data": "create",  # 'type': i_type,
            "ldapid": ldapid,  # 'from': date_from, 'to': date_to,
            # 'entity': entity, #'extIds': ['a', 'b', 'c'],
            "halId_s": "nullNone",
            "idRef": "nullNone",
            "orcId": "nullNone",
            "autres": "nullNone",
            "form": forms.CreateCredentials(),
            "iDhalerror": id_halerror,
        },
    )


def check(request):
    """
    Gestion de la page gérant l'affichage des données utilisateur ainsi que la vérification des données récupérées sur HAL afin d'affiner les résultats affichés par SoVisu
    """
    if request.user.is_authenticated and (
        request.user.get_username() == "visiteur"
        or request.user.get_username() == "guestUtln"
    ):
        return redirect("unknown")

    if "struct" in request.GET:
        struct = str(request.GET["struct"])
    else:
        struct = -1

    if "type" in request.GET and "id" in request.GET:
        i_type = request.GET["type"]
        p_id = request.GET["id"]

    elif request.user.is_authenticated:
        basereverse = "check"
        default_data = "credentials"
        return default_checker(request, basereverse, default_data)

    else:  # retour à l'ancien système et redirect unknown s'il n'est pas identifié et les i_type et p_id ne sont pas connu
        return redirect("unknown")

    if "data" in request.GET:
        data = request.GET["data"]
    else:
        data = -1
    # /

    if data == -1:
        return render(
            request,
            "create.html",
            {
                "data": create,
                # 'type': i_type, 'id': p_id, 'from': date_from, 'to': date_to,
                "form": forms.CreateCredentials(),
            },
        )

    # Get scope data
    key, search_id, index_pattern, ext_key, scope_param = get_scope_data(i_type, p_id)

    res = es.search(index=f"{struct}-{search_id}{index_pattern}", body=scope_param)
    # on pointe sur index générique, car pas de LabHalId ?

    try:
        entity = res["hits"]["hits"][0]["_source"]
    except:
        return redirect("unknown")
    # /

    # Get first submittedDate_tdate date
    field = "harvested_from_ids"
    if i_type == "rsr":
        start_date_param = esActions.date_p(field, entity["halId_s"])

        try:
            res = es.search(
                index=f"{struct}-{entity['labHalId']}-researchers-{p_id}-documents",
                body=start_date_param,
            )
            start_date = res["hits"]["hits"][0]["_source"]["submittedDate_tdate"]
        except:
            start_date = "2000"
    elif i_type == "lab":
        start_date_param = esActions.date_p(field, entity["halStructId"])

        try:
            res = es.search(
                index=f"{struct}-{entity['halStructId']}-laboratories-documents",
                body=start_date_param,
            )
            start_date = res["hits"]["hits"][0]["_source"]["submittedDate_tdate"]
        except:
            start_date = "2000"
    else:
        return redirect("unknown")
    # /

    # Get date parameters
    date_from, date_to = get_date(request, start_date)
    # /

    hastoconfirm = False
    validate = False
    if i_type == "rsr":
        field = "authIdHal_s"
        hastoconfirm_param = esActions.confirm_p(field, entity["halId_s"], validate)

        # devrait être scindé en deux ex.count qui diffèrent selon lab ou rsr dans les if précédent
        #  par ex pour == if i_type == "rsr": : es.count(index=struct  + "-" + entity['halStructId']+"-"researchers-" + entity["ldapId"] +"-documents", body=hastoconfirm_param)['count'] > 0:
    elif i_type == "lab":
        field = "labStructId_i"
        hastoconfirm_param = esActions.confirm_p(field, entity["halStructId"], validate)

    else:
        return redirect("unknown")

    if es.count(index=f"{struct}*-documents", body=hastoconfirm_param)["count"] > 0:
        # devrait être scindé en deux ex.count qui diffèrent selon lab ou rsr dans les if précédent
        #  par ex pour == if i_type == "lab": : es.count(index=struct  + "-" + entity['halStructId']+"-documents", body=hastoconfirm_param)['count'] > 0:
        hastoconfirm = True

    print(f"hastoconfirm = {hastoconfirm}")

    if data == "state":
        field = "labHalId"
        rsr_param = esActions.scope_p(field, p_id)

        count = es.count(index="*-researchers", body=rsr_param)["count"]

        rsrs = es.search(index="*-researchers", body=rsr_param, size=count)

        rsrs_cleaned = []

        for result in rsrs["hits"]["hits"]:
            rsrs_cleaned.append(result["_source"])
        print(rsrs_cleaned)
        return render(
            request,
            "check.html",
            {
                "struct": struct,
                "data": data,
                "type": i_type,
                "id": p_id,
                "from": date_from,
                "to": date_to,
                "entity": entity,
                "researchers": rsrs_cleaned,
                "startDate": start_date,
                "hasToConfirm": hastoconfirm,
                "timeRange": f"from:'{date_from}',to:'{date_to}'",
            },
        )

    if data == "-1" or data == "credentials":
        if i_type == "rsr":
            orcid = ""
            if "orcId" in entity:
                orcid = entity["orcId"]
            if "orcId" in request.GET:
                orcid = request.GET["orcId"]
            function = 0
            if "function" in entity:
                function = entity["function"]

            return render(
                request,
                "check.html",
                {
                    "struct": struct,
                    "data": data,
                    "type": i_type,
                    "id": p_id,
                    "from": date_from,
                    "to": date_to,
                    "entity": entity,
                    "extIds": ["a", "b", "c"],
                    "form": forms.ValidCredentials(
                        halId_s=entity["halId_s"],
                        aurehalId=entity["aurehalId"],
                        idRef=entity["idRef"],
                        orcId=orcid,
                        function=function,
                    ),
                    "startDate": start_date,
                    "hasToConfirm": hastoconfirm,
                    "timeRange": f"from:'{date_from}',to:'{date_to}'",
                },
            )

        if i_type == "lab":
            return render(
                request,
                "check.html",
                {
                    "struct": struct,
                    "data": data,
                    "type": i_type,
                    "id": p_id,
                    "from": date_from,
                    "to": date_to,
                    "entity": entity,
                    "form": forms.ValidLabCredentials(
                        halStructId=entity["halStructId"],
                        rsnr=entity["rsnr"],
                        idRef=entity["idRef"],
                    ),
                    "startDate": start_date,
                    "hasToConfirm": hastoconfirm,
                    "timeRange": f"from:'{date_from}',to:'{date_to}'",
                },
            )

    elif data == "research-description":
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
        return render(
            request,
            "check.html",
            {
                "struct": struct,
                "data": data,
                "type": i_type,
                "id": p_id,
                "from": date_from,
                "to": date_to,
                "entity": entity,
                "extIds": ["a", "b", "c"],
                "form": forms.SetResearchDescription(
                    guidingKeywords=guidingKeywords,
                    research_summary=research_summary,
                    research_projectsInProgress=research_projects_in_progress,
                    research_projectsAndFundings=research_projects_and_fundings,
                ),
                "startDate": start_date,
                "guidingKeywords": guidingKeywords,
                "research_summary": research_summary,
                "research_projectsInProgress": research_projects_in_progress,
                "research_projectsAndFundings": research_projects_and_fundings,
                "hasToConfirm": hastoconfirm,
                "timeRange": f"from:'{date_from}',to:'{date_to}'",
            },
        )

    elif data == "expertise":
        if "validation" in request.GET:
            validation = request.GET["validation"]

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
                                if (
                                    "state" in children2.keys()
                                    and children2["state"] == validate
                                ):
                                    concepts.append(
                                        {
                                            "id": children2["id"],
                                            "label_fr": "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- "
                                            + children2["label_fr"],
                                            "state": validate,
                                        }
                                    )

        return render(
            request,
            "check.html",
            {
                "struct": struct,
                "data": data,
                "type": i_type,
                "id": p_id,
                "from": date_from,
                "to": date_to,
                "validation": validation,
                "entity": entity,
                "concepts": concepts,
                "startDate": start_date,
                "hasToConfirm": hastoconfirm,
                "timeRange": f"from:'{date_from}',to:'{date_to}'",
            },
        )

    elif data == "guiding-domains":
        domains = halConcepts.concepts()

        guiding_domains = []

        if "guidingDomains" in entity:
            guiding_domains = entity["guidingDomains"]

        return render(
            request,
            "check.html",
            {
                "struct": struct,
                "data": data,
                "type": i_type,
                "id": p_id,
                "from": date_from,
                "to": date_to,
                "entity": entity,
                "domains": domains,
                "guidingDomains": guiding_domains,
                "startDate": start_date,
                "hasToConfirm": hastoconfirm,
                "timeRange": f"from:'{date_from}',to:'{date_to}'",
            },
        )

    elif data == "references":
        if "validation" in request.GET:
            validation = request.GET["validation"]

            if validation == "1":
                validate = True
            elif validation == "0":
                validate = False
            else:
                return redirect("unknown")
        else:
            return redirect("unknown")

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
        print(ref_param)

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

        return render(
            request,
            "check.html",
            {
                "struct": struct,
                "data": data,
                "type": i_type,
                "id": p_id,
                "from": date_from,
                "to": date_to,
                "validation": validation,
                "entity": entity,
                "hasToConfirm": hastoconfirm,
                "references": references_cleaned,
                "startDate": start_date,
                "timeRange": f"from:'{date_from}',to:'{date_to}'",
            },
        )

    else:
        return redirect("unknown")


def dashboard(request):
    """
    Gestion de la page affichant les tableaux de bord sous Kibana
    """
    # Get parameters
    if "struct" in request.GET:
        struct = str(request.GET["struct"])
    else:
        struct = -1

    if "ldapid" in request.GET:
        ldapid = request.GET["ldapid"]
    else:
        ldapid = None

    if (
        "type" in request.GET and "id" in request.GET
    ):  # réutilisation de l'ancien système
        i_type = request.GET["type"]
        p_id = request.GET["id"]

    elif request.user.is_authenticated:
        basereverse = "dashboard"
        return default_checker(request, basereverse)

    else:  # retour à l'ancien système et redirect unknown s'il n'est pas identifié et les i_type et p_id ne sont pas connu
        return redirect("unknown")
    # /

    # Get scope data
    key, search_id, index_pattern, ext_key, scope_param = get_scope_data(i_type, p_id)

    res = es.search(index=f"{struct}-{search_id}{index_pattern}", body=scope_param)
    # on pointe sur index générique, car pas de LabHalId ?
    try:
        entity = res["hits"]["hits"][0]["_source"]
    except:
        return redirect("unknown")
    # /

    hastoconfirm = False

    validate = False
    if i_type == "rsr":
        field = "authIdHal_s"
        hastoconfirm_param = esActions.confirm_p(field, entity["halId_s"], validate)

        # devrait être scindé en deux ex.count qui diffèrent selon lab ou rsr dans les if précédent
        #  par ex pour == if i_type == "rsr": : es.count(index=struct  + "-" + entity['halStructId']+"-"researchers-" +
        #  entity["ldapId"] +"-documents", body=hastoconfirm_param)['count'] > 0:
    elif i_type == "lab":
        field = "labStructId_i"
        hastoconfirm_param = esActions.confirm_p(field, entity["halStructId"], validate)
    else:
        return redirect("unknown")

    if (
        es.count(index=f"{struct}*-documents", body=hastoconfirm_param)["count"] > 0
    ):  # devrait être scindé en deux ex.count qui diffèrent selon lab ou rsr dans les if précédent
        #  par ex pour == if i_type == "lab": : es.count(index=struct  + "-" + entity['halStructId']+"-documents", body=hastoconfirm_param)['count'] > 0:
        hastoconfirm = True

    # Get first submittedDate_tdate date
    dash = ""
    start_date_param = ""
    if i_type == "rsr":
        indexsearch = (
            f"{struct}-{entity['labHalId']}-researchers-{entity['ldapId']}-documents"
        )
        try:
            start_date_param = esActions.date_all()
            res = es.search(index=indexsearch, body=start_date_param)

        except:
            start_date_param.pop("sort")
            res = es.search(index=indexsearch, body=start_date_param)

        filtrechercheur = f'_index: "{indexsearch}"'
        filtre_lab_a = ""
        filtre_lab_b = ""
    elif i_type == "lab":
        field = "harvested_from_ids"
        start_date_param = esActions.date_p(field, entity["halStructId"])
        if "dash" in request.GET:
            dash = request.GET["dash"]
        else:
            dash = "membres"
        res = es.search(
            index=f"{struct}-{p_id}-laboratories-documents", body=start_date_param
        )
        filtrechercheur = ""
        filtre_lab_a = f'harvested_from_ids: "{p_id}"'
        filtre_lab_b = f'labHalId.keyword: "{p_id}"'
    else:
        return redirect("unknown")

    try:  # çà devrait pas être un min de date sur les résultats plutôt que le premier ?.???
        start_date = res["hits"]["hits"][0]["_source"]["producedDate_tdate"]
    except:
        start_date = "2000"
    # /

    # Get date parameters
    date_from, date_to = get_date(request, start_date)
    # /

    url = (
        viewsActions.vizualisation_url()
    )  # permet d'ajuster l'url des visualisations en fonction du build

    return render(
        request,
        "dashboard.html",
        {
            "ldapid": ldapid,
            "struct": struct,
            "type": i_type,
            "id": p_id,
            "from": date_from,
            "to": date_to,
            "dash": dash,
            "entity": entity,
            "hasToConfirm": hastoconfirm,
            "ext_key": ext_key,
            "key": entity[key],
            "filterRsr": filtrechercheur,
            "filterlabA": filtre_lab_a,
            "filterlabB": filtre_lab_b,
            "url": url,
            "startDate": start_date,
            "timeRange": f"from:'{date_from}',to:'{date_to}'",
        },
    )


def references(request):
    """
    Gestion de la page affichant les références du profil sélectionné
    """
    # Get parameters
    if "struct" in request.GET:
        struct = str(request.GET["struct"])
    else:
        struct = -1

    if "ldapid" in request.GET:
        ldapid = request.GET["ldapid"]
    else:
        ldapid = None

    if (
        "type" in request.GET and "id" in request.GET
    ):  # réutilisation de l'ancien système
        i_type = request.GET["type"]
        p_id = request.GET["id"]

    elif request.user.is_authenticated:
        basereverse = "references"
        return default_checker(request, basereverse)

    else:  # retour à l'ancien système et redirect unknown s'il n'est pas identifié et les i_type et p_id ne sont pas connu
        return redirect("unknown")

    if "filter" in request.GET:
        i_filter = request.GET["filter"]
    else:
        i_filter = -1

    # /

    # Get scope data
    key, search_id, index_pattern, ext_key, scope_param = get_scope_data(i_type, p_id)

    res = es.search(index=f"{struct}-{search_id}{index_pattern}", body=scope_param)
    # on pointe sur index générique, car pas de LabHalId ?

    try:
        entity = res["hits"]["hits"][0]["_source"]
    except:
        return redirect("unknown")
    # /

    # Get first submittedDate_tdate date
    field = "harvested_from_ids"

    if i_type == "rsr":
        start_date_param = esActions.date_p(field, entity["halId_s"])

        res = es.search(
            index=f"{struct}-{entity['labHalId']}-researchers-{entity['ldapId']}-documents",
            body=start_date_param,
        )  # labHalId est-il là ?
    elif i_type == "lab":
        start_date_param = esActions.date_p(field, entity["halStructId"])

        res = es.search(
            index=f"{struct}-{p_id}-laboratories-documents", body=start_date_param
        )

    start_date = res["hits"]["hits"][0]["_source"]["submittedDate_tdate"]
    # /
    # Get date parameters
    date_from, date_to = get_date(request, start_date)
    # /

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
    # /
    return render(
        request,
        "references.html",
        {
            "ldapid": ldapid,
            "struct": struct,
            "filter": i_filter,
            "type": i_type,
            "id": p_id,
            "from": date_from,
            "to": date_to,
            "entity": entity,
            "hasToConfirm": hastoconfirm,
            "references": references_cleaned,
            "startDate": start_date,
            "timeRange": f"from:'{date_from}',to:'{date_to}'",
        },
    )


@xframe_options_exempt
def terminology(request):
    """
    Gestion de la page affichant les domaines d'expertise du profil sélectionné
    """
    # Get parameters
    if "struct" in request.GET:
        struct = str(request.GET["struct"])
    else:
        struct = -1

    if "ldapid" in request.GET:
        ldapid = request.GET["ldapid"]
    else:
        ldapid = None

    if (
        "type" in request.GET and "id" in request.GET
    ):  # réutilisation de l'ancien système
        i_type = request.GET["type"]
        p_id = request.GET["id"]

    elif request.user.is_authenticated:
        basereverse = "terminology"
        return default_checker(request, basereverse)

    else:  # retour à l'ancien système et redirect unknown s'il n'est pas identifié et les i_type et p_id ne sont pas connu
        return redirect("unknown")

    if "export" in request.GET:
        export = request.GET["export"]
    else:
        export = False
    # /

    # Get scope data
    key, search_id, index_pattern, ext_key, scope_param = get_scope_data(i_type, p_id)

    res = es.search(index=f"{struct}-{search_id}{index_pattern}", body=scope_param)
    # on pointe sur index générique, car pas de LabHalId ?
    try:
        entity = res["hits"]["hits"][0]["_source"]
    except:
        return redirect("unknown")
    # /

    hastoconfirm = False

    validate = False
    field = "harvested_from_ids"

    if i_type == "rsr":
        hastoconfirm_param = esActions.confirm_p(field, entity["halId_s"], validate)

    elif i_type == "lab":
        hastoconfirm_param = esActions.confirm_p(field, entity["halStructId"], validate)
    else:
        return redirect("unknown")

    if es.count(index="*-documents", body=hastoconfirm_param)["count"] > 0:
        hastoconfirm = True

    # Get first submittedDate_tdate date
    field = "harvested_from_ids"

    if i_type == "rsr":
        start_date_param = esActions.date_p(field, entity["halId_s"])

    elif i_type == "lab":
        start_date_param = esActions.date_p(field, entity["halStructId"])
    else:
        return redirect("unknown")

    res = es.search(index=f"{struct}-*-documents", body=start_date_param)
    start_date = res["hits"]["hits"][0]["_source"]["submittedDate_tdate"]
    # /

    # Get date parameters
    date_from, date_to = get_date(request, start_date)
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
            print(children["id"])
            state = "invalidated"
            if "researchers" in children:
                for rsr in children["researchers"]:
                    print(rsr)
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

    if export:
        return render(
            request,
            "terminology_ext.html",
            {
                "ldapid": ldapid,
                "struct": struct,
                "type": i_type,
                "id": p_id,
                "from": date_from,
                "to": date_to,
                "entity": entity,
                "hasToConfirm": hastoconfirm,
                "startDate": start_date,
                "timeRange": f"from:'{date_from}',to:'{date_to}'",
            },
        )
    else:
        return render(
            request,
            "terminology.html",
            {
                "ldapid": ldapid,
                "struct": struct,
                "type": i_type,
                "id": p_id,
                "from": date_from,
                "to": date_to,
                "entity": entity,
                "hasToConfirm": hastoconfirm,
                "startDate": start_date,
                "timeRange": f"from:'{date_from}',to:'{date_to}'",
            },
        )


def wordcloud(request):
    """
    Gestion de la page affichant sous forme de wordcloud les mots clés représentant le domaine de recherche du profil sélectionné (sous Kibana)
    """
    # Get parameters
    if "struct" in request.GET:
        struct = str(request.GET["struct"])
    else:
        struct = -1

    lang_options = [
        "ALL",
        "FR",
        "EN",
    ]  # Permet la création des onglets dans l'affichage de Sovisu. À remplacer plus tard par une création dynamique, mais les dashboards doivent être modifiés en conséquence également
    lang = "ALL"
    if (
        "lang" in request.GET
    ):  # Permet de limiter le choix de langue afin que Sovisu affiche toujours quelque chose. Dans le cas ou la langue demandée n'est pas dans les options initiales => le paramètre renvoyé est all.
        temp_lang = str(request.GET["lang"])
        if temp_lang in lang_options:
            lang = temp_lang

    if "ldapid" in request.GET:
        ldapid = request.GET["ldapid"]
    else:
        ldapid = None

    if (
        "type" in request.GET and "id" in request.GET
    ):  # réutilisation de l'ancien système
        i_type = request.GET["type"]
        p_id = request.GET["id"]

    elif request.user.is_authenticated:
        basereverse = "wordcloud"
        return default_checker(request, basereverse)

    else:  # retour à l'ancien système et redirect unknown s'il n'est pas identifié et les i_type et p_id ne sont pas connu
        return redirect("unknown")
    # /

    # Get scope data
    # l'ext_key n'est pas utilisé dans cette fonction
    key, search_id, index_pattern, ext_key, scope_param = get_scope_data(i_type, p_id)

    res = es.search(index=f"{struct}-{search_id}{index_pattern}", body=scope_param)
    # on pointe sur index générique, car pas de LabHalId ?

    try:
        entity = res["hits"]["hits"][0]["_source"]
    except:
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
        start_date_param = esActions.date_p(field, entity["halId_s"])
        indexsearch = (
            f"{struct}-{entity['labHalId']}-researchers-{entity['ldapId']}-documents"
        )
        filtrechercheur = f'_index: "{indexsearch}"'
        filtrelab = ""

    elif i_type == "lab":
        start_date_param = esActions.date_p(field, entity["halStructId"])
        indexsearch = f"{struct}-{entity['halStructId']}-laboratories-documents"
        filtrechercheur = ""
        filtrelab = f'_index: "{indexsearch}"'
    else:
        return redirect("unknown")

    res = es.search(index=f"{struct}*-documents", body=start_date_param)
    start_date = res["hits"]["hits"][0]["_source"]["submittedDate_tdate"]
    # /

    # Get date parameters
    date_from, date_to = get_date(request, start_date)
    # /

    url = (
        viewsActions.vizualisation_url()
    )  # permet d'ajuster l'url des visualisations en fonction du build

    return render(
        request,
        "wordcloud.html",
        {
            "ldapid": ldapid,
            "struct": struct,
            "type": i_type,
            "id": p_id,
            "from": date_from,
            "to": date_to,
            "entity": entity,
            "hasToConfirm": hastoconfirm,
            "filterRsr": filtrechercheur,
            "filterLab": filtrelab,
            "url": url,
            "lang_options": lang_options,
            "lang": lang,
            "startDate": start_date,
            "timeRange": f"from:'{date_from}',to:'{date_to}'",
        },
    )


def tools(request):
    """
    Gestion de la page "Outils", proposant des fonctionnalités pour les profils laboratoires. (Export HCERES, Cohésion des données)
    """
    start_time = datetime.now()
    # Get parameters
    if "struct" in request.GET:
        struct = str(request.GET["struct"])
    else:
        struct = -1

    if "ldapid" in request.GET:
        ldapid = request.GET["ldapid"]
    else:
        ldapid = None

    if (
        "type" in request.GET and "id" in request.GET
    ):  # réutilisation de l'ancien système
        i_type = request.GET["type"]
        p_id = request.GET["id"]

    elif request.user.is_authenticated:
        basereverse = "dashboard"
        return default_checker(request, basereverse)

    else:  # retour à l'ancien système et redirect unknown s'il n'est pas identifié et les i_type et p_id ne sont pas connu
        return redirect("unknown")
    # /

    # Get scope data
    # la fonction n'utilise que la partie i_type =="lab" de get_scope_data
    key, search_id, index_pattern, ext_key, scope_param = get_scope_data(i_type, p_id)

    res = es.search(index=f"{struct}-{search_id}{index_pattern}", body=scope_param)
    # on pointe sur index générique, car pas de LabHalId ?

    try:
        entity = res["hits"]["hits"][0]["_source"]
    except:
        return redirect("unknown")
    # /

    hastoconfirm = False

    validate = False
    if i_type == "lab":
        field = "labStructId_i"
        hastoconfirm_param = esActions.confirm_p(field, entity["halStructId"], validate)
    else:
        return redirect("unknown")

    if (
        es.count(index="*-documents", body=hastoconfirm_param)["count"] > 0
    ):  # devrait être scindé en deux ex.count qui diffèrent selon "lab" ou rsr dans les if précédent
        #  par ex pour == if i_type == "lab": : es.count(index=struct  + "-" + entity['halStructId']+"-documents", body=hastoconfirm_param)['count'] > 0:
        hastoconfirm = True

    # Get first submittedDate_tdate date
    if i_type == "lab":
        field = "harvested_from_ids"
        start_date_param = esActions.date_p(field, entity["halStructId"])

        res = es.search(
            index=f"{struct}-{p_id}-laboratories-documents", body=start_date_param
        )

    try:
        start_date = res["hits"]["hits"][0]["_source"]["submittedDate_tdate"]
    except:
        start_date = "2000"
    # /

    # Get date parameters
    date_from, date_to = get_date(request, start_date)
    # /

    if "data" in request.GET:
        data = request.GET["data"]
    else:
        data = "hceres"

    if data == "hceres" or data == -1:
        return render(
            request,
            "tools.html",
            {
                "ldapid": ldapid,
                "struct": struct,
                "data": data,
                "type": i_type,
                "id": p_id,
                "from": date_from,
                "to": date_to,
                "entity": entity,
                "hasToConfirm": hastoconfirm,
                "ext_key": ext_key,
                "key": entity[key],
                "startDate": start_date,
                "timeRange": f"from:'{date_from}',to:'{date_to}'",
            },
        )
    elif data == "consistency":
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

            # nombre de documents avec le nom de l'auteur coté lab par ex : (authIdHal_s : david-reymond)
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

        end_time = datetime.now()
        print(end_time - start_time)

        return render(
            request,
            "tools.html",
            {
                "ldapid": ldapid,
                "struct": struct,
                "data": data,
                "type": i_type,
                "id": p_id,
                "from": date_from,
                "to": date_to,
                "entity": entity,
                "consistency": consistencyvalues,
                "startDate": start_date,
                "hasToConfirm": hastoconfirm,
                "timeRange": f"from:'{date_from}',to:'{date_to}'",
            },
        )


def index(request):
    """
    Gestion des pages d'indexation des profils chercheurs et laboratoires
    """
    start = time.time()
    # Get parameters
    indexcat = request.GET["indexcat"]
    indexstruct = request.GET["indexstruct"]

    struct, i_type, p_id, ldapid = regular_get_parameters(request)

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
    # /
    print(f"For process: {time.time() - start} seconds")

    # Get date parameters
    start_date = "2000"
    date_from, date_to = get_date(request, start_date)
    # /

    if (
        i_type == -1 and p_id == -1
    ):  # Si l'i_type et l'id ne sont pas renseignés, ceux ci ne sont pas renvoyés
        # → évite des erreurs lors des vérifications pour les autres pages dans le cas d'un -1
        return render(
            request,
            "index.html",
            {
                "struct_tab": struct_tab,
                "entities": cleaned_entities,
                "indexcat": indexcat,
                "indexstruct": indexstruct,
                "ldapid": ldapid,
                "from": date_from,
                "to": date_to,
            },
        )
    else:  # L'i_type et l'id sont renvoyés dans la requète : persistence du profil choisi/connecté en amont.
        return render(
            request,
            "index.html",
            {
                "struct_tab": struct_tab,
                "entities": cleaned_entities,
                "type": i_type,
                "indexcat": indexcat,
                "indexstruct": indexstruct,
                "id": p_id,
                "struct": struct,
                "ldapid": ldapid,
                "from": date_from,
                "to": date_to,
            },
        )


def search(request):  # Revoir la fonction
    """
    Gestion de la page de recherche à partir de mots clés
    """
    date_param = {
        "aggs": {
            "min_date": {"min": {"field": "submittedDate_tdate"}},
        }
    }

    min_date = es.search(index="*-documents", body=date_param, size=0)["aggregations"][
        "min_date"
    ]["value_as_string"]

    # Get parameters
    struct, i_type, p_id, ldapid = regular_get_parameters(request)

    if "from" in request.GET:
        date_from = request.GET["from"]
    else:
        date_from = f"{min_date[0:4]}-01-01"

    if "to" in request.GET:
        date_to = request.GET["to"]
    else:
        date_to = datetime.today().strftime("%Y-%m-%d")

    if request.method == "POST":
        index = "*-researchers-*-doc*"  # request.POST.get("f_index")
        search = request.POST.get("f_search")

        # if "*-researchers-*-doc*" in index:  # == 'documents':
        search_param = {
            "query": {
                "bool": {
                    "must": [{"query_string": {"query": search}}],
                    "filter": [{"match": {"validated": "true"}}],
                }
            }
        }
        # elif "*-researchers" in index:  # =='researchers':
        #     search_param = {
        #         "query": {"query_string": {"query": search}}
        #     }
        # else:  # =='researchers': par défaut
        #     search_param = {
        #         "query": {"query_string": {"query": search}}
        #     }

        p_res = es.count(index=index, body=search_param)

        res = es.search(index=index, body=search_param, size=p_res["count"])

        res_cleaned = []

        for result in res["hits"]["hits"]:
            res_cleaned.append(result["_source"])
        messages.add_message(
            request,
            messages.INFO,
            'Résultats de la recherche "{}" dans la collection "{}"'.format(
                search, index
            ),
        )

        url = (
            viewsActions.vizualisation_url()
        )  # permet d'ajuster l'url des visualisations en fonction du build

        return render(
            request,
            "search2.html",
            {
                "struct": struct,
                "type": i_type,
                "id": p_id,
                "form": forms.Search(val=search),
                "count": p_res["count"],
                "url": url,
                "timeRange": f"from:'{date_from}',to:'{date_to}'",
                "filter": search,
                "index": index,
                "search": search,
                "results": res_cleaned,
                "from": date_from,
                "to": date_to,
                "startDate": min_date,
                "ldapid": ldapid,
            },
        )
    url = viewsActions.vizualisation_url()
    return render(
        request,
        "search2.html",
        {
            "struct": struct,
            "type": i_type,
            "id": p_id,
            "form": forms.Search(),
            "from": date_from,
            "to": date_to,
            "startDate": min_date,
            "filter": "",
            "url": url,
            "ldapid": ldapid,
        },
    )


def presentation(request):
    """
    Gestion de la page de présentation du projet
    """
    # Get parameters
    struct, i_type, p_id, ldapid = regular_get_parameters(request)
    # /
    # Get date parameters
    start_date = "2000"
    date_from, date_to = get_date(request, start_date)
    # /
    return render(
        request,
        "presentation.html",
        {
            "struct": struct,
            "type": i_type,
            "id": p_id,
            "ldapid": ldapid,
            "from": date_from,
            "to": date_to,
        },
    )


def ressources(request):
    """
    Gestion de la page des ressouces à destination des chercheurs
    """
    # Get parameters
    struct, i_type, p_id, ldapid = regular_get_parameters(request)
    # /
    # Get date parameters
    start_date = "2000"
    date_from, date_to = get_date(request, start_date)
    # /
    return render(
        request,
        "ressources.html",
        {
            "struct": struct,
            "type": i_type,
            "id": p_id,
            "ldapid": ldapid,
            "from": date_from,
            "to": date_to,
        },
    )


def faq(request):
    """
    Gestion de la page des questions fréquentes
    """
    # Get parameters
    struct, i_type, p_id, ldapid = regular_get_parameters(request)
    # /
    # Get date parameters
    start_date = "2000"
    date_from, date_to = get_date(request, start_date)
    # /
    return render(
        request,
        "faq.html",
        {
            "struct": struct,
            "type": i_type,
            "id": p_id,
            "ldapid": ldapid,
            "from": date_from,
            "to": date_to,
        },
    )


def useful_links(request):
    """
    Useful links page
    """
    # Get parameters
    struct, i_type, p_id, ldapid = regular_get_parameters(request)
    # /
    return render(
        request,
        "useful_links.html",
        {"struct": struct, "type": i_type, "id": p_id, "ldapid": ldapid},
    )


# /fonctions d'initialisation des pages


def default_checker(request, basereverse, default_data=None):
    """
    Vérifie si l'utilisateur est reconnu ou non avant de lui donner l'accès à certaines pages.
    """
    # utiliser cette fonction pour call log_checker
    # default_data ='' #use only if that parameter is needed
    # basereverse = ''
    # return default_checker(request, basereverse)

    try:
        p_id = request.user.get_display_id()  # cas log ?
    except:
        p_id = request.user.get_username()  # check si l'utilisateur est log
    # p_id = p_id.replace(viewsActions.patternCas, '').lower()

    if (
        p_id == "adminlab"
    ):  # si p_id adminlab on considère que son i_type par défaut est lab
        indexcat = "lab"
        base_url = reverse("index")
        query_string = urlencode({"indexcat": indexcat, "indexstruct": "198307662"})
        url = "{}?{}".format(base_url, query_string)
        return redirect(url)

    if p_id == "invitamu":
        indexcat = "rsr"
        base_url = reverse("index")
        query_string = urlencode({"indexcat": indexcat, "indexstruct": "130015332"})
        url = "{}?{}".format(base_url, query_string)
        return redirect(url)

    elif (
        not p_id == "adminlab"
        and not p_id == "visiteur"
        and not p_id == "invitamu"
        and not p_id == "guestUtln"
        and not p_id == -1
    ):
        # si ce n'est pas adminlab ni un visiteur → c'est un chercheur
        i_type = "rsr"
        base_url = reverse(
            basereverse
        )  # élément à changer en fonction de la fonction effectuant le call
        if default_data is not None:
            default_data = "credentials"
            query_string = urlencode({"type": i_type, "id": p_id, "data": default_data})
        else:
            query_string = urlencode({"type": i_type, "id": p_id})
        url = "{}?{}".format(base_url, query_string)
        return redirect(url)

    else:  # sinon il est inconnu et doit aller dans l'index pour faire ses choix, car on ne peut pas le suivre
        return redirect("unknown")


def regular_get_parameters(request):
    """
    Récupère les paramètres de la requête url
    """
    # utiliser cette fonction pour call regular_get_parameters
    # struct, i_type, p_id, ldapid = regular_get_parameters(request)

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


def get_scope_data(i_type, p_id):
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
    # la partie es.search n'est pas prise dans cette fonction, car la durée de la fonction principale passe de 2 à 4 s dans ce cas.

    return key, search_id, index_pattern, ext_key, scope_param


def get_date(request, start_date):
    """
    Retourne la date passée dans la requête url, sinon renseigne des dates par défaut.
    """
    # utiliser cette fonction pour call get_scope_data
    # date_from, date_to = get_date(request, start_date)

    if "from" in request.GET:
        date_from = request.GET["from"]
    else:
        date_from = f"{start_date[0:4]}-01-01"

    if "to" in request.GET:
        date_to = request.GET["to"]
    else:

        date_to = datetime.today().strftime("%Y-%m-%d")

    return date_from, date_to
