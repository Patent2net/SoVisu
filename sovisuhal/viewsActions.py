import json
from datetime import datetime
from io import BytesIO as B_io
from urllib.request import urlopen

import pandas as pd
from bs4 import BeautifulSoup
from decouple import config
from django.http import HttpResponse
from django.shortcuts import redirect
from uniauth.decorators import login_required

from elasticHal.libs import utils
from elasticHal.libs.archivesOuvertes import get_aurehalId, get_concepts_and_keywords

from . import settings
from .libs import esActions, hceres

mode = config("mode")  # Prod --> mode = 'Prod' en env Var
patternCas = "cas-universite-de-toulon-"  # motif à enlever aux identifiants CAS


# Connect to DB
es = esActions.es_connector()


@login_required
def admin_access_login(request):
    """
    Fonction gérant les accès à SoVisu
    """
    if not request.user.is_authenticated:
        return redirect("{}?next={}".format(settings.LOGIN_URL, "/"))
    else:
        auth_user = request.user.get_username().lower()

        if auth_user == "admin":
            return redirect("/index/?indexcat=lab&indexstruct=198307662")
        elif auth_user == "adminlab":
            return redirect("/index/?indexcat=lab&indexstruct=198307662")
        elif auth_user == "invitamu":
            return redirect("/index/?indexcat=rsr&indexstruct=130015332")
        elif auth_user == "visiteur":
            return redirect("/index/?indexcat=rsr&indexstruct=198307662")
        elif auth_user == "guestutln" or auth_user == "guestUtln":
            return redirect("/index/?indexcat=rsr&indexstruct=198307662")
        else:
            auth_user = auth_user.replace(patternCas, "").lower()

            field = "ldapId"  # TODO: Keep ldapId for UTLN, change to idhal for others
            scope_param = esActions.scope_p(field, auth_user)
            count = es.count(index="sovisu_searchers", query=scope_param)["count"]
            if count > 0:
                res = es.search(index="sovisu_searchers", query=scope_param, size=count)
                entity = res["hits"]["hits"][0]["_source"]
                struct = entity["structSirene"]
                user_token = entity["halId_s"]
                date_to = datetime.today().strftime("%Y-%m-%d")
                return redirect(
                    f"check/?struct={struct}&type=rsr&id={user_token}&from=1990-01-01&to={date_to}&data=credentials"
                )
            else:
                return redirect(
                    f"create/?ldapid={auth_user}&halId_s=nullNone&orcId=nullNone&idRef=nullNone"
                )


# TODO: Intégrer au CBV?
def validate_references(request):
    """
    Validation des références HAL
    """
    # Get parameters
    if "struct" in request.GET:
        struct = request.GET["struct"]
    else:
        return redirect("unknown")

    if "type" in request.GET:
        i_type = request.GET["type"]
    else:
        return redirect("unknown")

    if "id" in request.GET and "validation" in request.GET:
        p_id = request.GET["id"]
        validation = request.GET["validation"]
    else:
        return redirect("unknown")

    if "data" in request.GET:
        data = request.GET["data"]
    else:
        data = -1

    if "from" in request.GET:
        date_from = request.GET["from"]
    else:
        date_from = "2000-01-01"

    if "to" in request.GET:
        date_to = request.GET["to"]
    else:
        date_to = datetime.today().strftime("%Y-%m-%d")

    if int(validation) == 0:
        validate = True
    elif int(validation) == 1:
        validate = False
    else:
        return redirect("unknown")

    update_doc = {
        "sovisu_validated": validate
    }

    # Get scope information
    if i_type == "rsr":
        index_name = "sovisu_searchers"
    elif i_type == "lab":
        index_name = "sovisu_laboratories"
    else:
        return redirect("unknown")

    if request.method == "POST":
        to_validate = request.POST.get("toValidate", "").split(",")
        for sovisu_id in to_validate:
            es.update(
                index=index_name,
                refresh="wait_for",
                id=sovisu_id,
                doc=update_doc,
            )
    return redirect(
        f"/check/?struct={struct}&type={i_type}"
        + f"&id={p_id}&from={date_from}&to={date_to}&data={data}&validation={validation}"
    )


def validate_guiding_domains(request):
    """
    Validation des domaines de guidance
    """
    # Get parameters
    if "struct" in request.GET:
        struct = request.GET["struct"]
    else:
        return redirect("unknown")

    if "type" in request.GET and "id" in request.GET:
        i_type = request.GET["type"]
        p_id = request.GET["id"]
    else:
        return redirect("unknown")

    if "data" in request.GET:
        data = request.GET["data"]
    else:
        data = -1

    if "from" in request.GET:
        date_from = request.GET["from"]
    else:
        date_from = "2000-01-01"

    if "to" in request.GET:
        date_to = request.GET["to"]
    else:
        date_to = datetime.today().strftime("%Y-%m-%d")

    if request.method == "POST":
        to_validate = request.POST.get("toValidate", "").split(",")

        if i_type == "rsr":
            elastic_index = "test_researchers"

        elif i_type == "lab":
            elastic_index = "test_laboratories"
        else:
            return redirect("unknown")

        es.update(
            index=elastic_index,
            refresh="wait_for",
            id=p_id,
            doc={"guidingDomains": to_validate},
        )

    return redirect(
        f"/check/?struct={struct}&type={i_type}&id={p_id}&from={date_from}&to={date_to}&data={data}"
    )


def validate_expertise(request):
    """
    Validation des domaines d'expertise
    """
    # Get parameters
    if "struct" in request.GET:
        struct = request.GET["struct"]
    else:
        return redirect("unknown")

    if "type" in request.GET:
        i_type = request.GET["type"]
    else:
        return redirect("unknown")

    if "id" in request.GET and "validation" in request.GET:
        p_id = request.GET["id"]
        validation = request.GET["validation"]
    else:
        return redirect("unknown")

    if "data" in request.GET:
        data = request.GET["data"]
    else:
        data = -1

    if "from" in request.GET:
        date_from = request.GET["from"]
    else:
        date_from = "2000-01-01"

    if "to" in request.GET:
        date_to = request.GET["to"]
    else:
        date_to = datetime.today().strftime("%Y-%m-%d")

    if int(validation) == 0:
        validate_status = "to_validate"
    elif int(validation) == 1:
        validate_status = "to_remove"
    else:
        return redirect("unknown")

    if request.method == "POST":
        # get values sent via the form
        concepts_update = request.POST.get("toInvalidate", "").split(",")

        expertise_update = []

        for concept_id in concepts_update:
            # get the id of the expertise related to the concept
            expertise_id = concept_id.split(".", 1)[0]

            existing_item = next(
                (item for item in expertise_update if item["id"] == expertise_id), None
            )
            if existing_item:
                existing_item["children"].append({"id": concept_id})
            else:
                expertise_update.append({"id": expertise_id, "children": [{"id": concept_id}]})

        searcher_response = es.get(index="test_researchers", id=p_id)
        searcher_response = searcher_response["_source"]["SearcherProfile"][0]["validated_concepts"]
        updated_concepts = []

        if validate_status == "to_validate":  # If the post come from invalidated list

            # get the already validated_concepts as base
            updated_concepts = searcher_response
            # Load expertises file
            scope_param = esActions.scope_all()
            expertise_count = es.count(index="test_expertises", query=scope_param)["count"]
            expertises_list = es.search(
                index="test_expertises", query=scope_param, size=expertise_count
            )

            for expertise in expertises_list["hits"]["hits"]:
                expertise = expertise["_source"]
                id_to_check = expertise["id"]

                for update in expertise_update:
                    if update["id"] == id_to_check:
                        update["label_fr"] = expertise.get("label_fr")
                        update["label_en"] = expertise.get("label_en")

                        children = expertise.get("children", [])
                        for child in children:
                            child_id = child.get("id")
                            child_existing_item = next(
                                (
                                    child_item
                                    for child_item in update["children"]
                                    if child_item["id"] == child_id
                                ),
                                None,
                            )
                            # Update the existing child item in check_values with label information
                            if child_existing_item:
                                child_existing_item["label_en"] = child.get("label_en")
                                child_existing_item["label_fr"] = child.get("label_fr")

            for concept in expertise_update:
                concept_id = concept['id']
                concept_children = concept['children']

                existing_concept = None
                for validated_concept in updated_concepts:
                    if validated_concept['id'] == concept_id:
                        existing_concept = validated_concept
                        break

                if existing_concept is None:
                    updated_concepts.append(concept)
                else:
                    for child in concept_children:
                        existing_child = next((c for c in existing_concept['children'] if
                                               c.get('id') == child['id']), None)
                        if existing_child is None:
                            existing_concept['children'].append(child)

        elif validate_status == "to_remove":
            # Iterate over validated_concepts to remove concepts from expertises
            for expertise in searcher_response:

                if expertise["id"] in [item["id"] for item in expertise_update]:
                    children = expertise.get("children", [])

                    validated_children_ids = [
                        child_item["id"]
                        for item in expertise_update
                        for child_item in item.get("children", [])
                    ]

                    updated_children = [
                        child for child in children if child["id"] not in validated_children_ids
                    ]

                    expertise["children"] = updated_children

                # Delete the expertise if no concepts are associated anymore
                if expertise.get("children", []):
                    updated_concepts.append(expertise)

        else:
            return redirect("unknown")

        update_script = {
            "source": "for (profile in ctx._source.SearcherProfile) {"
                      " if (profile.ldapId == params.ldapId) "
                      "{ profile.validated_concepts = params.validated_concepts } }",
            "lang": "painless",
            "params": {"ldapId": p_id, "validated_concepts": updated_concepts},
        }

        es.update(index="test_researchers", id=p_id, script=update_script, refresh="wait_for")

    return redirect(
        f"/check/?struct={struct}&type={i_type}"
        + f"&id={p_id}&from={date_from}&to={date_to}&data={data}&validation={validation}"
    )



@login_required()
def validate_credentials(request):
    """
    Validation des identifiants
    """
    # Get parameters
    if "struct" in request.GET:
        struct = request.GET["struct"]
    else:
        return redirect("unknown")

    if "type" in request.GET and "id" in request.GET:
        i_type = request.GET["type"]
        p_id = request.GET["id"]
    else:
        return redirect("unknown")

    if "data" in request.GET:
        data = request.GET["data"]
    else:
        data = -1

    if "from" in request.GET:
        date_from = request.GET["from"]
    else:
        date_from = "2000-01-01"

    if "to" in request.GET:
        date_to = request.GET["to"]
    else:
        date_to = datetime.today().strftime("%Y-%m-%d")

    if request.method == "POST":
        if i_type == "rsr":
            idref = request.POST.get("f_IdRef")
            orcid = request.POST.get("f_orcId")
            function = request.POST.get("f_status")

            res = es.get(index="sovisu_searchers", id=p_id)
            try:
                entity = res["_source"]
            except IndexError:
                return redirect("unknown")

            aurehalId = ""
            if "aurehalId" in entity:
                aurehalId = entity["aurehalId"]

            aurehalId_get = get_aurehalId(entity["halId_s"])
            if aurehalId != aurehalId_get:
                aurehalId = aurehalId_get
                entity["aurehalId"] = aurehalId

            # TODO: supprimer Concepts sur le long terme dans la fonction.
            #  Doit passer dans SearcherProfile. Et principalement géré par test_expertises
            es.update(
                index="sovisu_searchers",
                refresh="wait_for",
                id=p_id,
                doc={
                    "aurehalId": aurehalId,
                    "idRef": idref,
                    "orcId": orcid,
                    "validated": True,
                    "function": function,
                },
            )

        if i_type == "lab":
            rsnr = request.POST.get("f_rsnr")
            idref = request.POST.get("f_IdRef")

            es.update(
                index="test_laboratories",
                refresh="wait_for",
                id=p_id,
                doc={"rsnr": rsnr, "idRef": idref, "validated": True},
            )

    return redirect(
        f"/check/?struct={struct}&type={i_type}&id={p_id}&from={date_from}&to={date_to}&data={data}"
    )


def validate_research_description(request):
    """
    Validation de la description de recherche
    """
    # Get parameters
    if "struct" in request.GET:
        struct = request.GET["struct"]
    else:
        return redirect("unknown")

    if "type" in request.GET and "id" in request.GET:
        i_type = request.GET["type"]
        p_id = request.GET["id"]
    else:
        return redirect("unknown")

    if "data" in request.GET:
        data = request.GET["data"]
    else:
        data = -1

    if "from" in request.GET:
        date_from = request.GET["from"]
    else:
        date_from = "2000-01-01"

    if "to" in request.GET:
        date_to = request.GET["to"]
    else:
        date_to = datetime.today().strftime("%Y-%m-%d")

    if request.method == "POST":
        guiding_keywords = request.POST.get("f_guidingKeywords").split(";")
        research_summary = request.POST.get("f_research_summary")
        research_projects_in_progress = request.POST.get("f_research_projectsInProgress")
        research_projects_and_fundings = request.POST.get("f_research_projectsAndFundings")

        soup = BeautifulSoup(research_summary, "html.parser")
        research_summary_raw = soup.getText().replace("\n", " ")

        soup = BeautifulSoup(research_projects_in_progress, "html.parser")
        research_projects_in_progress_raw = soup.getText().replace("\n", " ")

        soup = BeautifulSoup(research_projects_and_fundings, "html.parser")
        research_projects_and_fundings_raw = soup.getText().replace("\n", " ")

        if i_type == "rsr":
            es.update(
                index="test_researchers",
                refresh="wait_for",
                id=p_id,
                doc={
                    "research_summary": research_summary,
                    "research_summary_raw": research_summary_raw,
                    "research_projectsInProgress": research_projects_in_progress,
                    "research_projectsInProgress_raw": research_projects_in_progress_raw,
                    "research_projectsAndFundings": research_projects_and_fundings,
                    "research_projectsAndFundings_raw": research_projects_and_fundings_raw,
                    "research_updatedDate": datetime.today().isoformat(),
                    "guidingKeywords": guiding_keywords,
                },
            )

        elif i_type == "lab":
            es.update(
                index="test_laboratories",
                refresh="wait_for",
                id=p_id,
                doc={"guidingKeywords": guiding_keywords},
            )

    return redirect(
        f"/check/?struct={struct}&type={i_type}&id={p_id}&from={date_from}&to={date_to}&data={data}"
    )


def refresh_aurehal_id(request):
    """
    Mise à jour de l'id aurehal
    """
    # Get parameters
    if "struct" in request.GET:
        struct = request.GET["struct"]
    else:
        return redirect("unknown")

    if "type" in request.GET and "id" in request.GET:
        i_type = request.GET["type"]
        p_id = request.GET["id"]
    else:
        return redirect("unknown")

    if "data" in request.GET:
        data = request.GET["data"]
    else:
        data = -1

    if "from" in request.GET:
        date_from = request.GET["from"]
    else:
        date_from = "2000-01-01"

    if "to" in request.GET:
        date_to = request.GET["to"]
    else:
        date_to = datetime.today().strftime("%Y-%m-%d")

    scope_param = esActions.scope_p("_id", p_id)

    res = es.search(index="test_researchers", query=scope_param)
    try:
        entity = res["hits"]["hits"][0]["_source"]
    except IndexError:
        return redirect("unknown")

    aurehal_id = get_aurehalId(entity["halId_s"])
    concepts = []
    if aurehal_id != -1:
        archives_ouvertes_data = get_concepts_and_keywords(aurehal_id)
        concepts = utils.filter_concepts(archives_ouvertes_data["concepts"], validated_ids=[])

    es.update(
        index="test_researchers",
        refresh="wait_for",
        id=p_id,
        doc={"aurehalId": aurehal_id, "concepts": concepts},
    )

    return redirect(
        f"/check/?struct={struct}&type={i_type}&id={p_id}&from={date_from}&to={date_to}&data={data}"
    )


def update_members(request):
    """
    Permet la mise à jour du profil utilisateur
    """
    # Get parameters
    if "struct" in request.GET:
        struct = request.GET["struct"]
    else:
        return redirect("unknown")

    if "type" in request.GET and "id" in request.GET:
        i_type = request.GET["type"]
        p_id = request.GET["id"]
    else:
        return redirect("unknown")

    if "data" in request.GET:
        data = request.GET["data"]
    else:
        data = -1

    if "from" in request.GET:
        date_from = request.GET["from"]
    else:
        date_from = "2000-01-01"

    if "to" in request.GET:
        date_to = request.GET["to"]
    else:
        date_to = datetime.today().strftime("%Y-%m-%d")

    if request.method == "POST":
        to_update = request.POST.get("toUpdate", "").split(",")

        for element in to_update:
            element = element.split(":")
            scope_param = esActions.scope_p("_id", element[0])

            # attention multi univ la...
            res = es.search(index="test_researchers", query=scope_param)
            try:
                entity = res["hits"]["hits"][0]["_source"]
            except IndexError:
                return redirect(
                    f"/check/?struct={struct}"
                    + f"&type={i_type}&id={p_id}&from={date_from}&to={date_to}&data={data}"
                )

            es.update(
                index=res["hits"]["hits"][0]["_index"],
                refresh="wait_for",
                id=entity["ldapId"],
                doc={"axis": element[1]},
            )

    return redirect(
        f"/check/?struct={struct}&type={i_type}&id={p_id}&from={date_from}&to={date_to}&data={data}"
    )


# TODO: voir pour intégrer à checkview dans view_cbv.py?
def update_authorship(request):
    """
    Met à jour l'autorat des documents d'un utlisateur après vérification de ce dernier
    """
    # Get parameters
    if "struct" in request.GET:
        struct = request.GET["struct"]
    else:
        return redirect("unknown")

    if "type" in request.GET and "id" in request.GET:
        i_type = request.GET["type"]
        p_id = request.GET["id"]
    else:
        return redirect("unknown")

    if "data" in request.GET:
        data = request.GET["data"]
    else:
        data = -1

    if "from" in request.GET:
        date_from = request.GET["from"]
    else:
        date_from = "2000-01-01"

    if "to" in request.GET:
        date_to = request.GET["to"]
    else:
        date_to = datetime.today().strftime("%Y-%m-%d")

    try:
        to_process = json.loads(request.POST.get("toProcess", ""))
        for doc in to_process:
            print(doc)
            # update in researcher's collection

            update_doc = {
                "sovisu_authorship": doc["sovisu_authorship"]
            }

            es.update(
                index="sovisu_searchers",
                refresh="wait_for",
                id=doc["sovisu_id"],
                doc=update_doc,
            )

    except IndexError:
        pass

    return redirect(
        f"/check/?struct={struct}"
        + f"&type={i_type}&id={p_id}&from={date_from}&to={date_to}&data={data}&validation=1"
    )


def export_hceres_xls(request):
    """
    Export des données de l'HCERES d'un laboratoire sous fichier Excel (XLS)
    """
    # Get parameters
    if "id" in request.GET:
        p_id = request.GET["id"]
    else:
        return redirect("unknown")

    scope_param = esActions.scope_p("halStructId", p_id)

    key = "halStructId"
    ext_key = "harvested_from_ids"

    res = es.search(index="test_laboratories", query=scope_param)
    try:
        entity = res["hits"]["hits"][0]["_source"]
    except IndexError:
        return redirect("unknown")

    # Acquisition des chercheurs à traiter
    # toProcess = json.loads(request.POST.get("toProcess", ""))
    # toProcess_extra_cleaned = []
    # toProcess_extra = request.POST.get("toProcess_extra", "").splitlines()
    # for line in toProcess_extra:
    #     values = line.split(";")
    #     toProcess_extra_cleaned.append({"halId": values[0], "axis": values[1],
    #     "function": values[2], "scope": values[3]})
    #
    # toProcess.extend(toProcess_extra_cleaned)
    scope_bool_type = "filter"
    validate = True
    date_range_type = "publicationDate_tdate"
    date_from = "2016-01-01"
    date_to = "2021-12-31"
    ref_param = esActions.ref_p(
        scope_bool_type,
        ext_key,
        entity[key],
        validate,
        date_range_type,
        date_from,
        date_to,
    )

    count = es.count(index="test_publications", query=ref_param)["count"]

    references = es.search(index="test_publications", query=ref_param, size=count)

    references_cleaned = []

    for ref in references["hits"]["hits"]:
        references_cleaned.append(ref["_source"])

    sort_results = hceres.sort_references(references_cleaned, entity["halStructId"])

    art_df = sort_results[0]
    book_df = sort_results[1]
    conf_df = sort_results[2]
    hdr_df = sort_results[3]

    art_df = art_df.fillna("")
    book_df = book_df.fillna("")
    conf_df = conf_df.fillna("")
    hdr_df = hdr_df.fillna("")

    if not (conf_df.columns == "doiId_s").any():
        conf_df["doiId_s"] = " "
    if not (hdr_df.columns == "defenseDateY_i").any():
        hdr_df["defenseDateY_i"] = " "
    if not (book_df.columns == "isbn_s").any():
        book_df["isbn_s"] = ""

    output = B_io()

    writer = pd.ExcelWriter(output, engine="openpyxl")
    if len(art_df.index) > 0:
        art_df[
            [
                "authfullName_s",
                "title_s",
                "journalTitle_s",
                "volFull_s",
                "page_s",
                "publicationDateY_i",
                "doiId_s",
                "team",
                "hasPhDCandidate",
                "hasAuthorship",
                "openAccess_bool_s",
            ]
        ].to_excel(writer, "ART", index=False)
    else:
        art_df.to_excel(writer, "ART", index=False)
    if len(book_df.index) > 0:
        book_df[
            [
                "authfullName_s",
                "title_s",
                "journalTitle_s",
                "volFull_s",
                "page_s",
                "publicationDateY_i",
                "isbn_s",
                "team",
                "hasPhDCandidate",
                "hasAuthorship",
                "openAccess_bool_s",
            ]
        ].to_excel(writer, "OUV", index=False)
    else:
        book_df.to_excel(writer, "OUV", index=False)
    if len(conf_df.index) > 0:
        if "page_s" in conf_df:
            conf_df[
                [
                    "authfullName_s",
                    "title_s",
                    "journalTitle_s",
                    "volFull_s",
                    "page_s",
                    "publicationDateY_i",
                    "doiId_s",
                    "team",
                    "conferenceTitle_s",
                    "conferenceDate_s",
                    "hasPhDCandidate",
                    "hasAuthorship",
                    "openAccess_bool_s",
                ]
            ].to_excel(writer, "CONF", index=False)
        else:
            conf_df[
                [
                    "authfullName_s",
                    "title_s",
                    "journalTitle_s",
                    "volFull_s",
                    "publicationDateY_i",
                    "doiId_s",
                    "team",
                    "conferenceTitle_s",
                    "conferenceDate_s",
                    "hasPhDCandidate",
                    "hasAuthorship",
                    "openAccess_bool_s",
                ]
            ].to_excel(writer, "CONF", index=False)
    else:
        conf_df.to_excel(writer, "CONF", index=False)
    if len(hdr_df.index) > 0:
        hdr_df[["authfullName_s", "defenseDateY_i", "team"]].to_excel(writer, "HDR", index=False)
    else:
        hdr_df.to_excel(writer, "HDR", index=False)
    writer.close()

    output.seek(0)

    filename = f"hceres_{entity['acronym']}.xlsx"
    response = HttpResponse(
        output,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = "attachment; filename=%s" % filename

    return response


def idhal_checkout(idhal):
    """
    Vérifie si le halId renseigné existe
    """
    # idhal = "luc-quoniam" valeur test
    html = f"https://api.archives-ouvertes.fr/search/?q=authIdHal_s:{idhal}"
    response = urlopen(html)

    data_json = json.loads(response.read())

    print(data_json)
    print(data_json["response"]["numFound"])
    if data_json["response"]["numFound"] == 0:
        confirmation = 0
    else:
        confirmation = 1
    return confirmation


def vizualisation_url():
    """
    Permet d'ajuster l'affichage des visualisations Kibana
    À intégrer dans les consts
    """
    url = "/kibana"
    return url
