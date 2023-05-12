# from libs import hal, utils, unpaywall, scanR
import datetime
import json
import re

import dateutil.parser
from celery import shared_task
from celery_progress.backend import ProgressRecorder
from dateutil.relativedelta import relativedelta
from decouple import config
from django.shortcuts import redirect
from elasticsearch import helpers
from ldap3 import ALL, Connection, Server

from elasticHal.libs import (
    doi_enrichissement,
    hal,
    keyword_enrichissement,
    location_docs,
    utils,
)
from elasticHal.libs.archivesOuvertes import get_aurehalId, get_concepts_and_keywords

from . import esActions

# from uniauth.decorators import login_required


mode = config("mode")  # Prod --> mode = 'Prod' en env Var

# Connect to DB
es = esActions.es_connector()


# @shared_task(bind=True)
def indexe_chercheur(structid, ldapid, labo_accro, labhalid, idhal, idref, orcid):  # self,
    """
    Indexe un chercheur dans Elasticsearch
    """
    #   progress_recorder = ProgressRecorder(self)
    #   progress_recorder.set_progress(0, 10, description='récupération des données LDAP')
    if mode == "Prod":
        server = Server("ldap.univ-tln.fr", get_info=ALL)
        conn = Connection(
            server,
            "cn=Sovisu,ou=sysaccount,dc=ldap-univ-tln,dc=fr",
            config("ldappass"),
            auto_bind=True,
        )  # recup des données ldap
        conn.search(
            "dc=ldap-univ-tln,dc=fr",
            "(&(uid=" + ldapid + "))",
            attributes=[
                "displayName",
                "mail",
                "typeEmploi",
                "ustvstatus",
                "supannaffectation",
                "supanncodeentite",
                "supannEntiteAffectationPrincipale",
                "labo",
            ],
        )
        dico = json.loads(conn.response_to_json())["entries"][0]
    else:
        dico = {
            "attributes": {
                "displayName": "REYMOND David",
                "labo": [],
                "mail": ["david.reymond@univ-tln.fr"],
                "supannAffectation": ["IMSIC", "IUT TC"],
                "supannEntiteAffectationPrincipale": "IUTTCO",
                "supanncodeentite": [],
                "typeEmploi": "Enseignant Chercheur Titulaire",
                "ustvStatus": ["OFFI"],
            },
            "dn": "uid=dreymond,ou=Personnel,ou=people,dc=ldap-univ-tln,dc=fr",
        }
        ldapid = "dreymond"
    labo = labhalid

    extrait = dico["dn"].split("uid=")[1].split(",")
    chercheur_type = extrait[1].replace("ou=", "")
    suppan_id = extrait[0]
    if suppan_id != ldapid:
        print("aille", ldapid, " --> ", ldapid)
    nom = dico["attributes"]["displayName"]
    emploi = dico["attributes"]["typeEmploi"]
    mail = dico["attributes"]["mail"]
    if "supannAffectation" in dico["attributes"].keys():
        supann_affect = dico["attributes"]["supannAffectation"]
    else:
        supann_affect = []

    if "supannEntiteAffectationPrincipale" in dico["attributes"].keys():
        supann_princ = dico["attributes"]["supannEntiteAffectationPrincipale"]
    else:
        supann_princ = []

    if not len(nom) > 0:
        nom = [""]
    elif not len(emploi) > 0:
        emploi = [""]
    elif not len(mail) > 0:
        mail = [""]

    chercheur = dict()
    chercheur["name"] = nom
    chercheur["type"] = chercheur_type
    chercheur["function"] = emploi
    chercheur["mail"] = mail[0]
    chercheur["orcId"] = orcid
    chercheur["lab"] = labo_accro  # acronyme
    chercheur["supannAffectation"] = ";".join(supann_affect)
    chercheur["supannEntiteAffectationPrincipale"] = supann_princ
    chercheur["firstName"] = chercheur["name"].split(" ")[1]
    chercheur["lastName"] = chercheur["name"].split(" ")[0]

    # Chercheur["aurehalId"]

    # creation des index
    #  progress_recorder.set_progress(5, 10, description='creation des index')
    if not es.indices.exists(index=structid + "-structures"):
        es.indices.create(index=structid + "-structures")
    if not es.indices.exists(index=structid + "-" + labo + "-researchers"):
        es.indices.create(index=structid + "-" + labo + "-researchers")
        es.indices.create(
            index=structid + "-" + labo + "-researchers-" + ldapid + "-documents"
        )  # -researchers" + row["ldapId"] + "-documents
    else:
        if not es.indices.exists(
            index=structid + "-" + labo + "-researchers-" + ldapid + "-documents"
        ):
            es.indices.create(
                index=structid + "-" + labo + "-researchers-" + ldapid + "-documents"
            )  # -researchers" + row["ldapId"] + "-documents" ?

    chercheur["structSirene"] = structid
    chercheur["labHalId"] = labo
    chercheur["validated"] = False
    chercheur["ldapId"] = ldapid
    chercheur["Created"] = datetime.datetime.now().isoformat()

    # New step ?

    if idhal != "":
        aurehal = get_aurehalId(idhal)
        # integration contenus
        archives_ouvertes_data = get_concepts_and_keywords(aurehal)
    else:  # sécurité, le code n'est pas censé être lancé par create car vérification du champ idhal
        return redirect("unknown")
        # retourne sur check() ?

    chercheur["halId_s"] = idhal
    chercheur["validated"] = False
    chercheur["aurehalId"] = aurehal  # heu ?
    chercheur["concepts"] = archives_ouvertes_data["concepts"]
    chercheur["guidingKeywords"] = []
    chercheur["idRef"] = idref
    chercheur["axis"] = labo_accro

    # Chercheur["mappings"]: {
    #     "_default_": {
    #         "_timestamp": {
    #             "enabled": "true",
    #             "store": "true",
    #             "path": "plugins.time_stamp.string",
    #             "format": "yyyy-MM-dd HH:m:ss"
    #         }
    #     }}
    res = es.index(
        index=chercheur["structSirene"] + "-" + chercheur["labHalId"] + "-researchers",
        id=chercheur["ldapId"],
        body=json.dumps(chercheur),
        refresh="wait_for",
    )
    print("statut de la création d'index: ", res["result"])
    return chercheur


@shared_task(bind=True)
def collecte_docs(self, chercheur, overwrite=False):  # self,
    """
    Collecte les notices liées à un chercheur
    "overwrite" : remet les valeurs pour l'ensemble du document à ses valeurs initiales.
    """
    progress_recorder = ProgressRecorder(self)
    docs = hal.find_publications(chercheur["halId_s"], "authIdHal_s")

    progress_recorder.set_progress(0, len(docs), description="récupération des données HAL")
    # Insert documents collection
    for num, doc in enumerate(docs):
        location_docs.generate_countrys_fields(doc)
        doc = doi_enrichissement.docs_enrichissement_doi(doc)

        if "fr_abstract_s" in doc.keys():
            if isinstance(doc["fr_abstract_s"], list):
                doc["fr_abstract_s"] = "/n".join(doc["fr_abstract_s"])
            if len(doc["fr_abstract_s"]) > 100:
                doc["fr_entites"] = keyword_enrichissement.return_entities(
                    doc["fr_abstract_s"], "fr"
                )
                doc["fr_teeft_keywords"] = keyword_enrichissement.keyword_from_teeft(
                    doc["fr_abstract_s"], "fr"
                )

        if "en_abstract_s" in doc.keys():
            if isinstance(doc["en_abstract_s"], list):
                doc["en_abstract_s"] = "/n".join(doc["en_abstract_s"])
            if len(doc["en_abstract_s"]) > 100:
                doc["en_entites"] = keyword_enrichissement.return_entities(
                    doc["en_abstract_s"], "en"
                )
                doc["en_teeft_keywords"] = keyword_enrichissement.keyword_from_teeft(
                    doc["en_abstract_s"], "en"
                )

        doc["_id"] = doc["docid"]

        doc["harvested_from"] = "researcher"

        doc["harvested_from_ids"] = []
        doc["harvested_from_label"] = []

        doc["harvested_from_ids"].append(chercheur["halId_s"])

        doc["records"] = []

        doc["MDS"] = utils.calculate_mds(doc)

        doc["postprint_embargo"], doc["preprint_embargo"] = should_be_open(doc)

        doc["Created"] = datetime.datetime.now().isoformat()

        # add a category to make differentiation in text_* index pattern
        doc["category"] = "Notice"

        # add a common SearcherProfile Key who should serve has common key between index
        doc["SearcherProfile"] = []

        # check if the document already exist and edit fields depending on overwrite state
        doc_param = esActions.scope_p("_id", doc["_id"])
        count_document = es.count(index="test_publications", query=doc_param)

        # Create the records of the searchers linked to the document.
        for idhal in doc["authIdHal_s"]:
            validated_concepts = ""
            validated = "unassigned"
            authorship = ""

            # get validated_concepts of the searcher if registered in SoVisu
            searcher_param = esActions.scope_p("SearcherProfile.halId_s", idhal)
            count_searcher = es.count(index="test_researchers", query=searcher_param)
            if count_searcher["count"] > 0:
                searcher_data = es.search(index="test_researchers", query=searcher_param)
                searcher_data = searcher_data["hits"]["hits"][0]["_source"]["SearcherProfile"][0]
                validated_concepts = searcher_data["validated_concepts"]

            if overwrite or count_document["count"] == 0:
                if count_searcher["count"] > 0:
                    validated = "True"
                # check authorship
                if doc["authIdHal_s"].index(idhal) == 0:
                    authorship = "firstAuthor"
                if doc["authIdHal_s"].index(idhal) == len(doc["authIdHal_s"]) - 1:
                    authorship = "lastAuthor"
            else:
                document_data = es.search(index="test_publications", query=doc_param)
                document_data = document_data["hits"]["hits"][0]["_source"]

                for searcher in document_data["SearcherProfile"]:
                    if searcher["halId_s"] == idhal:
                        validated = searcher["validated"]
                        authorship = searcher["authorship"]

            # add the record of the Searcher in the document
            doc["SearcherProfile"].append(
                {
                    "halId_s": idhal,
                    "ldapId": chercheur["ldapId"]
                    if chercheur["halId_s"] == idhal
                    else "unassigned",
                    "validated_concepts": validated_concepts,
                    "validated": validated,
                    "authorship": authorship,
                }
            )

        progress_recorder.set_progress(num, len(docs), description="(récolte)")

    helpers.bulk(es, docs, index="test_publications", refresh="wait_for")

    progress_recorder.set_progress(num, len(docs), description="(indexation)")
    return chercheur


# TODO: intégrer dans utils.py après modification du module elasticHal
def should_be_open(notice):
    """
    Remplace should_be_open dans elasticHal/utils.py
    Calcul l'état de l'embargo d'un document
    À renommer en conséquence lors de l'intégration générale dans le code
    """
    # SHERPA/RoMEO embargo
    notice["postprint_embargo"] = None
    if (
        "fileMain_s" not in notice
        or notice["openAccess_bool"] is False
        or "linkExtUrl_s" not in notice
    ):
        if "journalSherpaPostPrint_s" in notice:
            if notice["journalSherpaPostPrint_s"] == "can":
                notice["postprint_embargo"] = "false"
            elif (
                notice["journalSherpaPostPrint_s"] == "restricted"
                and "publicationDate_tdate" in notice
                and "journalSherpaPostRest_s" in notice
            ):
                matches = re.finditer(
                    r"(\S+\s+){2}(?=embargo)", notice["journalSherpaPostRest_s"].replace("[", " ")
                )
                for match in matches:
                    duration = match.group().split(" ")[0]
                    if duration.isnumeric():
                        publication_date = dateutil.parser.parse(
                            notice["publicationDate_tdate"]
                        ).replace(tzinfo=None)

                        curr_date = datetime.now()
                        age = relativedelta(curr_date, publication_date)
                        age_in_months = age.years * 12 + age.months

                        if age_in_months > int(duration):
                            notice["postprint_embargo"] = "false"
                        else:
                            notice["postprint_embargo"] = "true"
            elif notice["journalSherpaPostPrint_s"] == "cannot":
                notice["postprint_embargo"] = "true"
            else:
                notice["postprint_embargo"] = None

    notice["preprint_embargo"] = None
    if (
        "fileMain_s" not in notice
        or notice["openAccess_bool"] is False
        or "linkExtUrl_s" not in notice
    ):
        if "journalSherpaPrePrint_s" in notice:
            if notice["journalSherpaPrePrint_s"] == "can":
                notice["preprint_embargo"] = "false"
            elif (
                notice["journalSherpaPrePrint_s"] == "restricted"
                and "journalSherpaPreRest_s" in notice
            ):
                if "Must obtain written permission from Editor" in notice["journalSherpaPreRest_s"]:
                    notice["preprint_embargo"] = "perm_from_editor"
            elif notice["journalSherpaPrePrint_s"] == "cannot":
                notice["preprint_embargo"] = "true"
            else:
                notice["preprint_embargo"] = None

    return notice["postprint_embargo"], notice["preprint_embargo"]
