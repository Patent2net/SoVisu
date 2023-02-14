import json
from datetime import datetime
from io import BytesIO as B_io
from urllib.request import urlopen

import pandas as pd
from bs4 import BeautifulSoup
from django.http import HttpResponse
from django.shortcuts import redirect

from elasticHal.libs import utils
from elasticHal.libs.archivesOuvertes import get_concepts_and_keywords, get_aurehalId
from sovisuhal.libs.elastichal import indexe_chercheur, collecte_docs
from . import settings
from .libs import esActions

try:
    from decouple import config
    from ldap3 import Server, Connection, ALL
    from uniauth.decorators import login_required

    mode = config("mode")  # Prod --> mode = 'Prod' en env Var

    patternCas = "cas-universite-de-toulon-"  # motif à enlever aux identifiants CAS

except:
    from django.contrib.auth.decorators import login_required

    mode = "Dev"
    patternCas = ""  # motif à enlever aux identifiants CAS

# Connect to DB
es = esActions.es_connector()


@login_required
def admin_access_login(request):
    """
    Fonction gérant les accès à SoVisu
    """
    if not request.user.is_authenticated:
        return redirect("%s?next=%s" % (settings.LOGIN_URL, "/"))
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

            field = "_id"
            scope_param = esActions.scope_p(field, auth_user)
            count = es.count(index="*-researchers", body=scope_param)["count"]
            if count > 0:
                res = es.search(index="*-researchers", body=scope_param, size=count)
                entity = res["hits"]["hits"][0]["_source"]
                struct = entity["structSirene"]
                date_to = datetime.today().strftime("%Y-%m-%d")
                return redirect(
                    f"check/?struct={struct}&type=rsr&id={auth_user}&from=1990-01-01&to={date_to}&data=credentials"
                )
            else:
                return redirect(
                    f"create/?ldapid={auth_user}&halId_s=nullNone&orcId=nullNone&idRef=nullNone"
                )


def create_credentials(request):
    """
    Fonction gérant la création du nouveau profil d'un chercheur à partir des données renseignées dans le formulaire CreateCredentials
    """
    ldapid = request.GET["ldapid"]
    idref = request.POST.get("f_IdRef")
    idhal = request.POST.get("f_halId_s")
    orcid = request.POST.get("f_orcId")

    tempo_lab = request.POST.get("f_labo")  # chaine de caractère
    tempo_lab = tempo_lab.replace("'", "")
    tempo_lab = tempo_lab.replace("(", "")
    tempo_lab = tempo_lab.replace(")", "")
    tempo_lab = tempo_lab.split(",")
    labo = tempo_lab[0].strip()  # halid
    accro_lab = tempo_lab[1].strip()
    # resultat

    idhal_test = idhal_checkout(idhal)

    if idhal_test == 0:
        print("idhal not found")
        return redirect(
            f"/create/?ldapid={ldapid}&halId_s=nullNone&orcId=nullNone&idRef=nullNone&iDhalerror=True"
        )

    else:
        print("idhal found")
        # création de l'entrée pour le chercheur dans Elastic
        chercheur = indexe_chercheur(ldapid, accro_lab, labo, idhal, idref, orcid)

        # récupération de la documentation de l'utilisateur
        collecte_docs(chercheur)
        # récupération du struct du nouveau profil pour la redirection
        field = "halId_s"
        scope_param = esActions.scope_p(field, idhal)
        count = es.count(index="*-researchers", body=scope_param)["count"]
        res = es.search(index="*-researchers", body=scope_param, size=count)
        entity = res["hits"]["hits"][0]["_source"]
        struct = entity["structSirene"]
        # /
        # name,type,function,mail,lab,supannAffectation,supannEntiteAffectationPrincipale,halId_s,labHalId,idRef,structDomain,firstName,lastName,aurehalId
        date_to = datetime.today().strftime("%Y-%m-%d")
        return redirect(
            f"/check/?struct={struct}&type=rsr&id={ldapid}&orcId={orcid}&from=1990-01-01&to={date_to}&data=credentials"
        )


# Redirects


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

    # Get scope information
    if i_type == "rsr":
        scope_param = esActions.scope_p("_id", p_id)

        res = es.search(index=f"{struct}-*-researchers", body=scope_param)
        try:
            entity = res["hits"]["hits"][0]["_source"]
        except Exception as e:
            print(e)
            return redirect("unknown")

        if request.method == "POST":
            to_validate = request.POST.get("toValidate", "").split(",")
            for docid in to_validate:
                es.update(
                    index=f"{struct}-{entity['labHalId']}-researchers-{entity['ldapId']}-documents",
                    refresh="wait_for",
                    id=docid,
                    body={"doc": {"validated": validate}},
                )
                try:
                    es.update(
                        index=f"{struct}-{entity['labHalId']}-laboratories-documents",
                        refresh="wait_for",
                        id=docid,
                        body={"doc": {"validated": validate}},
                    )
                except Exception as e:
                    print(f"{struct}-{entity['labHalId']}-laboratories-documents")
                    print(e)
                    pass  # doc du chercheur pas dans le labo

    if i_type == "lab":
        scope_param = esActions.scope_p("_id", p_id)

        res = es.search(index=f"{struct}-*-laboratories", body=scope_param)
        try:
            entity = res["hits"]["hits"][0]["_source"]
        except:
            return redirect("unknown")

        if request.method == "POST":
            to_validate = request.POST.get("toValidate", "").split(",")
            for docid in to_validate:
                es.update(
                    index=f"{struct}-{entity['halStructId']}-laboratories-documents",
                    refresh="wait_for",
                    id=docid,
                    body={"doc": {"validated": validate}},
                )

    return redirect(
        f"/check/?struct={struct}&type={i_type}&id={p_id}&from={date_from}&to={date_to}&data={data}&validation={validation}"
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
            scope_param = esActions.scope_p("_id", p_id)

            res = es.search(index=f"{struct}-*-researchers", body=scope_param)
            try:
                entity = res["hits"]["hits"][0]["_source"]
            except:
                return redirect("unknown")

            es.update(
                index=f"{struct}-{entity['labHalId']}-researchers",
                refresh="wait_for",
                id=p_id,
                body={"doc": {"guidingDomains": to_validate}},
            )

        if i_type == "lab":
            es.update(
                index=f"{struct}-{p_id}-laboratories",
                refresh="wait_for",
                id=p_id,
                body={"doc": {"guidingDomains": to_validate}},
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
        validate = "validated"
    elif int(validation) == 1:
        validate = "invalidated"
    else:
        return redirect("unknown")

    # Get scope information
    if i_type == "rsr":
        scope_param = esActions.scope_p("_id", p_id)

        res = es.search(index=f"{struct}-*-researchers", body=scope_param)
        try:
            entity = res["hits"]["hits"][0]["_source"]
        except:
            return redirect("unknown")

        index = f"{struct}-{entity['labHalId']}-researchers"
        lab_index = f"{struct}-{entity['labHalId']}-laboratories"

        # get tree from lab
        lab_scope_param = esActions.scope_p("_id", entity["labHalId"])

        res = es.search(index=f"{struct}*-laboratories", body=lab_scope_param)
        entity_lab = res["hits"]["hits"][0]["_source"]

        lab_tree = entity_lab["concepts"]

        if request.method == "POST":
            to_invalidate = request.POST.get("toInvalidate", "").split(",")

            for conceptid in to_invalidate:
                sid = conceptid.split(".")
                for children in entity["concepts"]["children"]:
                    if len(sid) >= 1 and sid[0] == children["id"]:
                        lab_tree = utils.append_to_tree(
                            children, entity, lab_tree, validate
                        )
                        children["state"] = validate

                    if "children" in children:
                        for children1 in children["children"]:
                            if len(sid) >= 2:
                                if sid[0] + "." + sid[1] == children1["id"]:
                                    lab_tree = utils.append_to_tree(
                                        children1, entity, lab_tree, validate
                                    )
                                    children1["state"] = validate

                            if "children" in children1:
                                for children2 in children1["children"]:
                                    if len(sid) >= 3:
                                        if (
                                            sid[0] + "." + sid[1] + "." + sid[2]
                                            == children2["id"]
                                        ):
                                            lab_tree = utils.append_to_tree(
                                                children2, entity, lab_tree, validate
                                            )
                                            children2["state"] = validate

            es.update(
                index=index,
                refresh="wait_for",
                id=entity["ldapId"],
                body={"doc": {"concepts": entity["concepts"]}},
            )

            es.update(
                index=lab_index,
                refresh="wait_for",
                id=entity["labHalId"],
                body={"doc": {"concepts": lab_tree}},
            )

    return redirect(
        f"/check/?struct={struct}&type={i_type}&id={p_id}&from={date_from}&to={date_to}&data={data}&validation={validation}"
    )


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

            scope_param = esActions.scope_p("_id", p_id)

            res = es.search(index=f"{struct}*-researchers", body=scope_param)
            try:
                entity = res["hits"]["hits"][0]["_source"]
                print(f"entity = {entity}")
            except:
                return redirect("unknown")

            print(f"{struct}-{entity['labHalId']}-researchers")

            if entity["aurehalId"] != "":
                print("initialize concept and keywords gathering")
                archives_ouvertes_data = get_concepts_and_keywords(entity["aurehalId"])
                archives_ouvertes_data = archives_ouvertes_data["concepts"]
                print(f"concepts: {archives_ouvertes_data}")
            else:
                print("no aurehalid available to gather")
                archives_ouvertes_data = ""

            es.update(
                index=f"{struct}-{entity['labHalId']}-researchers",
                refresh="wait_for",
                id=p_id,
                body={
                    "doc": {
                        "idRef": idref,
                        "orcId": orcid,
                        "validated": True,
                        "function": function,
                        "concepts": archives_ouvertes_data,
                    }
                },
            )

        if i_type == "lab":
            rsnr = request.POST.get("f_rsnr")
            idref = request.POST.get("f_IdRef")

            es.update(
                index=f"{struct}-{p_id}-laboratories",
                refresh="wait_for",
                id=p_id,
                body={"doc": {"rsnr": rsnr, "idRef": idref, "validated": True}},
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
        research_projects_in_progress = request.POST.get(
            "f_research_projectsInProgress"
        )
        research_projects_and_fundings = request.POST.get(
            "f_research_projectsAndFundings"
        )

        soup = BeautifulSoup(research_summary, "html.parser")
        research_summary_raw = soup.getText().replace("\n", " ")

        soup = BeautifulSoup(research_projects_in_progress, "html.parser")
        research_projects_in_progress_raw = soup.getText().replace("\n", " ")

        soup = BeautifulSoup(research_projects_and_fundings, "html.parser")
        research_projects_and_fundings_raw = soup.getText().replace("\n", " ")

        if i_type == "rsr":
            scope_param = esActions.scope_p("_id", p_id)

            res = es.search(index=f"{struct}*-researchers", body=scope_param)
            try:
                entity = res["hits"]["hits"][0]["_source"]
            except:
                return redirect("unknown")

            es.update(
                index=f"{struct}-{entity['labHalId']}-researchers",
                refresh="wait_for",
                id=p_id,
                body={
                    "doc": {
                        "research_summary": research_summary,
                        "research_summary_raw": research_summary_raw,
                        "research_projectsInProgress": research_projects_in_progress,
                        "research_projectsInProgress_raw": research_projects_in_progress_raw,
                        "research_projectsAndFundings": research_projects_and_fundings,
                        "research_projectsAndFundings_raw": research_projects_and_fundings_raw,
                        "research_updatedDate": datetime.today().isoformat(),
                        "guidingKeywords": guiding_keywords,
                    }
                },
            )

        elif i_type == "lab":
            es.update(
                index=f"{struct}-{str(p_id)}-laboratories",
                refresh="wait_for",
                id=p_id,
                body={"doc": {"guidingKeywords": guiding_keywords}},
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

    res = es.search(index=f"{struct}*-researchers", body=scope_param)
    try:
        entity = res["hits"]["hits"][0]["_source"]
    except:
        return redirect("unknown")

    aurehal_id = get_aurehalId(entity["halId_s"])
    concepts = []
    if aurehal_id != -1:
        archives_ouvertes_data = get_concepts_and_keywords(aurehal_id)
        concepts = utils.filter_concepts(
            archives_ouvertes_data["concepts"], validated_ids=[]
        )

    es.update(
        index=f"{struct}-{entity['labHalId']}-researchers",
        refresh="wait_for",
        id=p_id,
        body={"doc": {"aurehalId": aurehal_id, "concepts": concepts}},
    )

    return redirect(
        f"/check/?struct={struct}&type={i_type}&id={p_id}&from={date_from}&to={date_to}&data={data}"
    )


def force_update_references(request):
    """
    Force la mise à jour des références
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
        date_to = datetime.today().strftime("%Y-%m-%d")

    # if request.method == 'POST':
    # comprend pas pourquoi cette ligne d'autant qu'on récupère les paramètres sur GET....

    if i_type == "rsr":
        scope_param = esActions.scope_p("_id", p_id)

        res = es.search(index=f"{struct}*-researchers", body=scope_param)
        try:
            entity = res["hits"]["hits"][0]["_source"]
        except:
            return redirect("unknown")

        collecte_docs(entity)

    return redirect(
        f"/check/?struct={struct}&type={i_type}&id={p_id}&from={date_from}&to={date_to}&data=references&validation=1"
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
            res = es.search(index="*-researchers", body=scope_param)
            try:
                entity = res["hits"]["hits"][0]["_source"]
            except:
                return redirect(
                    f"/check/?struct={struct}&type={i_type}&id={p_id}&from={date_from}&to={date_to}&data={data}"
                )
            es.update(
                index=res["hits"]["hits"][0]["_index"],
                refresh="wait_for",
                id=entity["ldapId"],
                body={"doc": {"axis": element[1]}},
            )

    return redirect(
        f"/check/?struct={struct}&type={i_type}&id={p_id}&from={date_from}&to={date_to}&data={data}"
    )


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

    scope_param = esActions.scope_p("ldapId", p_id)

    res = es.search(index=f"{struct}-*-researchers", body=scope_param)
    try:
        entity = res["hits"]["hits"][0]["_source"]
    except:
        return redirect("unknown")

    try:
        to_process = json.loads(request.POST.get("toProcess", ""))
        for doc in to_process:
            # update in researcher's collection
            field = "_id"
            doc_param = esActions.scope_p(field, doc["docid"])

            res = es.search(
                index=f"{struct}-{entity['labHalId']}-researchers-{entity['ldapId']}-documents",
                body=doc_param,
            )
            if len(res["hits"]["hits"]) > 0:
                if "authorship" in res["hits"]["hits"][0]["_source"]:
                    authorship = res["hits"]["hits"][0]["_source"]["authorship"]
                    exists = False
                    for author in authorship:
                        if author["authIdHal_s"] == entity["halId_s"]:
                            exists = True
                            author["authorship"] = doc["authorship"]
                    if not exists:
                        authorship.append(
                            {
                                "authorship": doc["authorship"],
                                "authIdHal_s": entity["halId_s"],
                            }
                        )
                else:
                    authorship = [
                        {
                            "authorship": doc["authorship"],
                            "authIdHal_s": entity["halId_s"],
                        }
                    ]
            else:
                authorship = [
                    {"authorship": doc["authorship"], "authIdHal_s": entity["halId_s"]}
                ]

            es.update(
                index=f"{struct}-{entity['labHalId']}-researchers-{entity['ldapId']}-documents",
                refresh="wait_for",
                id=doc["docid"],
                body={"doc": {"authorship": authorship}},
            )

            # update in laboratory's collection
            field = "_id"
            doc_param = esActions.scope_p(field, doc["docid"])

            res = es.search(
                index=f"{struct}-{entity['labHalId']}-laboratories-documents",
                body=doc_param,
            )

            try:
                if len(res["hits"]["hits"]) > 0:
                    if "autorship" in res["hits"]["hits"][0]["_source"]:
                        authorship = res["hits"]["hits"][0]["_source"]["authorship"]
                        exists = False
                        for author in authorship:
                            if author["authIdHal_s"] == entity["halId_s"]:
                                exists = True
                                author["authorship"] = doc["authorship"]
                        if not exists:
                            authorship.append(
                                {
                                    "authorship": doc["authorship"],
                                    "authIdHal_s": entity["halId_s"],
                                }
                            )
                    else:
                        authorship = [
                            {
                                "authorship": doc["authorship"],
                                "authIdHal_s": entity["halId_s"],
                            }
                        ]
                else:
                    authorship = [
                        {
                            "authorship": doc["authorship"],
                            "authIdHal_s": entity["halId_s"],
                        }
                    ]

                es.update(
                    index=f"{struct}-{entity['labHalId']}-laboratories-documents",
                    refresh="wait_for",
                    id=doc["docid"],
                    body={"doc": {"authorship": authorship}},
                )
            except:
                print(f"docid {str(doc['docid'])} non trouvé dans l'index des labs...")
    except:
        pass

    return redirect(
        f"/check/?struct={struct}&type={i_type}&id={p_id}&from={date_from}&to={date_to}&data={data}&validation=1"
    )


def export_hceres_xls(request):
    """
    Export des données de l'HCERES d'un laboratoire sous fichier Excel (XLS)
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

    scope_param = esActions.scope_p("halStructId", p_id)

    key = "halStructId"
    ext_key = "harvested_from_ids"

    res = es.search(index=f"{struct}-{p_id}-laboratories", body=scope_param)
    try:
        entity = res["hits"]["hits"][0]["_source"]
    except:
        return redirect("unknown")

    # Acquisition des chercheurs à traiter
    # toProcess = json.loads(request.POST.get("toProcess", ""))
    # toProcess_extra_cleaned = []
    # toProcess_extra = request.POST.get("toProcess_extra", "").splitlines()
    # for line in toProcess_extra:
    #     values = line.split(";")
    #     toProcess_extra_cleaned.append({"halId": values[0], "axis": values[1], "function": values[2], "scope": values[3]})
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

    count = es.count(
        index=f"{struct}-{entity['halStructId']}-laboratories-documents", body=ref_param
    )["count"]
    print(f"{struct}-{entity['halStructId']}-laboratories-documents")
    print(count)
    references = es.search(
        index=f"{struct}-{entity['halStructId']}-laboratories-documents",
        body=ref_param,
        size=count,
    )

    from .libs import hceres

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
        hdr_df[["authfullName_s", "defenseDateY_i", "team"]].to_excel(
            writer, "HDR", index=False
        )
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
    Permet d'ajuster l'affichage des visualisations Kibana entre la version Dev et la version Prod
    """
    print("mode: ")
    print(mode)
    if mode == "dev":
        url = "http://127.0.0.1:5601/kibana"
        # url = "/kibana"
    else:
        url = "/kibana"

    return url
