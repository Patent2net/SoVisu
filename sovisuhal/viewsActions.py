import json
from datetime import datetime
from io import BytesIO as B_io
from urllib.request import urlopen

import pandas as pd

from django.http import HttpResponse
from django.shortcuts import redirect
from uniauth.decorators import login_required

from constants import SV_INDEX, TIMEZONE, SV_LAB_INDEX
from elasticHal.libs import utils
from elasticHal.libs.archivesOuvertes import get_aurehalId, get_concepts_and_keywords
from sovisuhal.libs.elastichal import creeFichesExpertise

from . import settings
from .libs import esActions, hceres

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
        default_redirect = "/structures_index/?indexcategory=laboratory"

        default_profiles = ["admin", "adminlab", "invitamu", "visiteur"]

        if auth_user in default_profiles:
            return redirect(default_redirect)
        else:
            auth_user = auth_user.replace(patternCas, "").lower()

            field = "ldapId"
            scope_param = esActions.scope_p(field, auth_user)
            count = es.count(index=SV_INDEX, query=scope_param)["count"]
            if count > 0:
                res = es.search(index=SV_INDEX, query=scope_param, size=count)
                entity = res["hits"]["hits"][0]["_source"]
                user_token = entity["halId_s"]
                date_to = datetime.now(tz=TIMEZONE).date().isoformat()
                return redirect(
                    f"check/?type=rsr&id={user_token}&from=1990-01-01&to={date_to}&data=credentials"
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
        date_to = datetime.now(tz=TIMEZONE).date().isoformat()

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
        index_name = SV_INDEX
    elif i_type == "lab":
        index_name = SV_LAB_INDEX
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
        f"/check/?type={i_type}"
        + f"&id={p_id}&from={date_from}&to={date_to}&data={data}&validation={validation}"
    )


def validate_guiding_domains(request):
    """
    Validation des domaines de guidance
    """
    # Get parameters

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
        date_to = datetime.now(tz=TIMEZONE).date().isoformat()

    if request.method == "POST":
        to_validate = request.POST.get("toValidate", "").split(",")
        aurehal = request.POST.get("aurehal")
        query = {"bool": {
            "must": [{"match": {"sovisu_category": "expertise"}}, {"match": {"idhal": p_id}}, ]}}

        if i_type == "rsr":
            elastic_index = SV_INDEX
            count = es.count(index=SV_INDEX, query=query)["count"]
            fichesExpertise = es.search(index=SV_INDEX, query=query, size=count)
            if fichesExpertise['_shards']['successful'] > 0:
                fichesExpertise = fichesExpertise['hits']['hits']

                dejaLa = [fiche["_source"]['chemin'].replace("domAurehal.", "") for fiche in
                          fichesExpertise if
                          fiche["_source"]['chemin'].replace("domAurehal.", "") in to_validate
                          and fiche["_source"]['validated']]
                if len(to_validate) != len(dejaLa):
                    dejaLaPasValid = [fiche for fiche in fichesExpertise if
                                      fiche["_source"]['chemin'].replace("domAurehal.",
                                                                         "") in to_validate
                                      and not fiche["_source"]['validated']]
                    # Mise à jour
                    for fiche in dejaLaPasValid:
                        if fiche["_source"]['origin'] != "datagouv":
                            fiche["_source"]['origin'] = "datagouv"
                            fiche["_source"]['validated'] = True
                            es.update(index=SV_INDEX, id=fiche["_id"], body=fiche["_source"])
                        to_validate.remove(fiche["_source"]['chemin'].replace("domAurehal.", ""))

                    creeFichesExpertise(idx=SV_INDEX, idHal=p_id, aureHal=aurehal,
                                        lstDom=[fic for fic in to_validate if
                                                fic not in dejaLa and fic not in dejaLaPasValid])
                # fichesExpertise ["_source"]["validated"]
            else:

                creeFichesExpertise(idx=SV_INDEX, idHal=p_id, aureHal=aurehal, lstDom=to_validate)
        elif i_type == "lab":

            elastic_index = "test_laboratories"
        else:
            return redirect("unknown")

        # es.update(
        #     index=elastic_index,
        #     refresh="wait_for",
        #     id=p_id,
        #     doc={"guidingDomains": to_validate},
        # )

    return redirect(
        f"/check/?type={i_type}&id={p_id}&from={date_from}&to={date_to}&data={data}"
    )


def validate_expertise(request):
    # TODO: intégrer à views_cbv
    """
    Validation des domaines d'expertise
    """
    # Get parameters

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
        date_to = datetime.now(tz=TIMEZONE).date().isoformat()

    if int(validation) == 0:  # validation is at 0 when page show unvalidated concepts
        update_doc = {
            "validated": True
        }
    elif int(validation) == 1:  # validation is at 1 when page show validated concepts
        update_doc = {
            "validated": False
        }
    else:
        return redirect("unknown")

    if request.method == "POST":
        # get values sent via the form
        concepts_to_update = request.POST.get("toInvalidate", "").split(",")

        for concept in concepts_to_update:
            es.update(index=SV_INDEX, refresh="wait_for", id=concept, doc=update_doc)

    return redirect(
        f"/check/?type={i_type}"
        + f"&id={p_id}&from={date_from}&to={date_to}&data={data}&validation={validation}"
    )


@login_required()
def validate_credentials(request):
    """
    Validation des identifiants
    """
    # Get parameters

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
        date_to = datetime.now(tz=TIMEZONE).date().isoformat()

    if request.method == "POST":
        if i_type == "rsr":
            idref = request.POST.get("f_IdRef")
            orcid = request.POST.get("f_orcId")
            function = request.POST.get("f_status")

            res = es.get(index=SV_INDEX, id=p_id)
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
                index=SV_INDEX,
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
        f"/check/?type={i_type}&id={p_id}&from={date_from}&to={date_to}&data={data}"
    )


def refresh_aurehal_id(request):
    """
    Mise à jour de l'id aurehal
    """
    # Get parameters

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
        date_to = datetime.now(tz=TIMEZONE).date().isoformat()

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
        f"/check/?type={i_type}&id={p_id}&from={date_from}&to={date_to}&data={data}"
    )


def update_members(request):
    """
    Permet la mise à jour du profil utilisateur
    """
    # Get parameters

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
        date_to = datetime.now(tz=TIMEZONE).date().isoformat()

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
                    f"/check/?type={i_type}&id={p_id}&from={date_from}&to={date_to}&data={data}"
                )

            es.update(
                index=res["hits"]["hits"][0]["_index"],
                refresh="wait_for",
                id=entity["ldapId"],
                doc={"axis": element[1]},
            )

    return redirect(
        f"/check/?type={i_type}&id={p_id}&from={date_from}&to={date_to}&data={data}"
    )


# TODO: voir pour intégrer à checkview dans view_cbv.py?
def update_authorship(request):
    """
    Met à jour l'autorat des documents d'un utlisateur après vérification de ce dernier
    """
    # Get parameters
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
        date_to = datetime.now(tz=TIMEZONE).date().isoformat()

    try:
        to_process = json.loads(request.POST.get("toProcess", ""))
        for doc in to_process:
            print(doc)
            # update in researcher's collection

            update_doc = {
                "sovisu_authorship": doc["sovisu_authorship"]
            }

            es.update(
                index=SV_INDEX,
                refresh="wait_for",
                id=doc["sovisu_id"],
                doc=update_doc,
            )

    except IndexError:
        pass

    return redirect(
        f"/check/?type={i_type}&id={p_id}&from={date_from}&to={date_to}&data={data}&validation=1"
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

    if "from" in request.GET:
        date_from = request.GET["from"]
    else:
        date_from = "2000-01-01"

    if "to" in request.GET:
        date_to = request.GET["to"]
    else:
        date_to = datetime.now(tz=TIMEZONE).date().isoformat()

    res = es.get(index=SV_LAB_INDEX, id=p_id)
    try:
        entity = res["_source"]
    except IndexError:
        return redirect("unknown")

    validate = True
    date_range_type = "publicationDate_tdate"

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
    count = es.count(index=SV_LAB_INDEX, query=query)["count"]

    references = es.search(index=SV_LAB_INDEX, query=query, size=count)

    references_cleaned = []

    for ref in references["hits"]["hits"]:
        references_cleaned.append(ref["_source"])

    sort_results = hceres.sort_references(references_cleaned, entity["docid"])

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

    filename = f"hceres_{entity['acronym_s']}.xlsx"
    response = HttpResponse(
        output,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f"attachment; filename={filename}"

    return response


# TODO: revoir pour fonctionner avec référentiel auteur au lieu de chercheur les documents
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


# TODO: Faire une fonction pour gérer les status validated de manière générale:
#  (passage "validated" de true à false)
