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


# TODO: Renommer Get_dico pour quelque chose de plus explicite
def get_dico(ldapid):
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

    return dico


# @shared_task(bind=True)
def indexe_chercheur(structid, ldapid, labo_accro, labhalid, idhal, idref, orcid):  # self,
    # TODO: séparer en fonctions distinctes chaque élément de la fonction:
    #  Modele: une fonction générale qui call chaque élément dans l'ordre souhaité (création fiche chercheur, puis fiche labo liée, puis récupération concepts liés
    """
    Indexe un chercheur dans Elasticsearch
    """

    # Get the basic information about the searcher
    dico = get_dico(ldapid)
    # -----------------

    extrait = dico["dn"].split("uid=")[1].split(",")
    chercheur_type = extrait[1].replace("ou=", "")
    suppan_id = extrait[0]
    if suppan_id != ldapid:
        print("aille", ldapid, " --> ", ldapid)

    nom = dico["attributes"]["displayName"] if len(dico["attributes"]["displayName"]) > 0 else [""]
    emploi = dico["attributes"]["typeEmploi"] if len(dico["attributes"]["typeEmploi"]) > 0 else [""]
    mail = dico["attributes"]["mail"] if len(dico["attributes"]["mail"]) > 0 else [""]

    supann_affect = []
    if "supannAffectation" in dico["attributes"].keys():
        supann_affect = dico["attributes"]["supannAffectation"]

    supann_princ = []
    if "supannEntiteAffectationPrincipale" in dico["attributes"].keys():
        supann_princ = dico["attributes"]["supannEntiteAffectationPrincipale"]

    # New step ?
    aurehal = ""

    if idhal != "":
        aurehal = get_aurehalId(idhal)

    searcher_notice = {
        "name": nom,
        "type": chercheur_type,
        "function": emploi,
        "mail": mail[0],
        "orcId": orcid,
        "lab": labo_accro,  # TODO: INTERET DE CETTE KEY?
        "supannAffectation": ";".join(supann_affect),
        "supannEntiteAffectationPrincipale": supann_princ,
        "firstName": nom.split(" ")[1],
        "lastName": nom.split(" ")[0],
        "structSirene": structid,
        "labHalId": labhalid,
        "validated": False,
        "ldapId": ldapid,
        "Created": datetime.datetime.now().isoformat(),
        "idhal": idhal,  # sert de clé pivot entre les docs, il faut être sûr que ce champ n'existe dans aucune des docs que l'on pourrait indexer
        "halId_s": idhal,
        "aurehalId": aurehal,
        "idRef": idref,
        "axis": labo_accro,  # TODO: INTERET DE CETTE KEY? contient la même chose que lab
        "sovisu_category": "searcher"
    }

    res = es.index(
        index="sovisu_searchers",
        id=idhal,
        document=searcher_notice,
        refresh="wait_for",
    )

    # integration contenus
    create_searcher_concept_notices(idhal, aurehal)
    create_searcher_structure_notices(idhal, labhalid)
    print("statut de la création d'index: ", res["result"])


@shared_task(bind=True)
def collecte_docs(self, chercheur, overwrite=False):  # self,
    """
    Collecte les notices liées à un chercheur
    "overwrite" : remet les valeurs pour l'ensemble du document à ses valeurs initiales.
    """
    progress_recorder = ProgressRecorder(self)
    idhal = chercheur["idhal"]
    docs = hal.find_publications(idhal, "authIdHal_s")

    progress_recorder.set_progress(0, len(docs), description="récupération des données HAL")
    # Insert documents collection

    for num, doc in enumerate(docs):
        # L'id du doc est associé à celui du chercheur dans ES
        # Chaque chercheur ses docs
        # ci après c'est supposé que ce sont des chaines de caractère. Il me semble qu'on avait eu des soucis !!!
        # doc["_id"] = doc["docid"] + '_' + chercheur["idhal"] #c'est son doc à lui. Pourront être rajoutés ses choix de mots clés etc
        # supression des références au _id : laissons elastic gérer. On utilise le docid du doc. l'idhal du chercheur
        changements = False
        check_existing_doc_id = f"{idhal}.{doc['halId_s']}"
        document_exist = es.exists(index="sovisu_searchers", id=check_existing_doc_id)
        if document_exist:
            existing_document = es.get(index="sovisu_searchers", id=check_existing_doc_id)
            existing_document = existing_document["_source"]

            doc["MDS"] = utils.calculate_mds(doc)

            if doc["MDS"] != existing_document["MDS"]:
                # SI le MDS a changé alors modif qualitative sur la notice
                changements = True
            else:
                doc = existing_document

        if not document_exist or changements:
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
                    doc["en_entites"] = keyword_enrichissement.return_entities(doc["en_abstract_s"],
                                                                               "en")
                    doc["en_teeft_keywords"] = keyword_enrichissement.keyword_from_teeft(
                        doc["en_abstract_s"], "en")
            # Nouveau aussi ci dessous
            doc["MDS"] = utils.calculate_mds(doc)
            doc["Created"] = datetime.datetime.now().isoformat()

        if not document_exist:
            doc["harvested_from"] = "researcher"  # inutile je pense
            doc[
                "harvested_from_ids"] = []  # du coup çà devient inutile car présent dans le docId Mais ...
            doc["harvested_from_label"] = []  # idem ce champ serait à virer
            doc["harvested_from_ids"].append(chercheur["idhal"])  # idem ici
            doc["records"] = []
            doc["sovisu_category"] = "notice"
            doc["sovisu_referentiel"] = "hal"
            doc["idhal"] = idhal,  # l'Astuce du
            doc["sovisu_id"] = f'{idhal}.{doc["halId_s"]}'
            doc["sovisu_validated"] = True
            doc["_id"] = f'{idhal}.{doc["halId_s"]}'
            authorship = ""
            # TODO: Revoir pour être plus fiable?
            if doc["authIdHal_s"].index(idhal) == 0:
                authorship = "firstAuthor"
            if doc["authIdHal_s"].index(idhal) == len(doc["authIdHal_s"]) - 1:
                authorship = "lastAuthor"

            doc["sovisu_authorship"] = authorship
        else:
            pass

        progress_recorder.set_progress(num, len(docs), description="(récolte)")

    helpers.bulk(es, docs, index="sovisu_searchers", refresh="wait_for")

    progress_recorder.set_progress(num, len(docs), description="(indexation)")
    return chercheur


# TODO: intégrer dans utils.py après modification du module elasticHal?
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

                        curr_date = datetime.datetime.now()
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


# TODO: Refactor that function
def create_searcher_concept_notices(idhal, aurehal):
    archives_ouvertes_data = get_concepts_and_keywords(aurehal)
    chercheur_concept = archives_ouvertes_data["concepts"]
    if len(chercheur_concept) > 0:
        # scope_param = scope_p("id", [exp['id'] for exp in chercheur_concept['children']])
        # scope_param =  {
        #     "terms": {
        #       "chemin": ["domAurehal."+exp['id'] for exp in chercheur_concept['children']]
        #     }
        #   }
        # AUCUN des deux scope ne remontent toutes les fiches domaine chercheur : elles n'existeent pas
        query = esActions.scope_all()
        count = es.count(index="domaine_hal_referentiel", query=query)["count"]
        # resDomainesRef = es.search(index="domaine_hal_referentiel", query=scope_param, size=count)
        toutRef = [truc['_source']['chemin'] for truc in
                   es.search(index="domaine_hal_referentiel", query={'match_all': {}}, size=count)[
                       'hits']['hits']]

        Vu = set()
        pasVu = set()
        idDomainChecheur = [exp['id'] for exp in chercheur_concept['children']]
        for ids in idDomainChecheur:
            ok = False
            for ch in toutRef:
                if ch.endswith(ids):
                    Vu.add(ch)
                    ok = True
            if not ok:
                pasVu.add(ids)
        for new in pasVu:
            print("Nouveau dans le dico ??? çà sort d'où ?", new)
        ####
        # Traitement des vus... matchés on recopie la fiche référentiel et on personnalise. Actuellement, on taggue

        lstReq = []
        for dom in Vu:
            lstReq.append({
                "match": {
                    "chemin": dom
                }
            })

        req = {
            "bool": {
                "should": lstReq,
                "minimum_should_match": 1,
                "must": [
                    {
                        "match_all": {}
                    }
                ]
            }
        }

        resDomainesRef = es.search(index="domaine_hal_referentiel", query=req)
        for fiche in resDomainesRef['hits']['hits']:
            newFiche = fiche['_source']
            newFiche['validated'] = False  # domaines pas validés par défaut
            # Id proposition : valider les domaines par défaut et laisser la possibilité d'en valider d'autres par explorateur d'arbre ?
            newFiche['idhal'] = idhal  # taggage, l'idhal sert de clé
            # Et rajouts besoins spécifiques (genre précisions / notes...)
            elastic_id = f"{idhal}.{newFiche['chemin']}"
            newFiche['sovisu_id'] = elastic_id
            # Puis on indexe la fiche
            es.index(index="sovisu_searchers", id=elastic_id, document=json.dumps(newFiche), refresh="wait_for",)


def create_searcher_structure_notices(idhal, labhalid):
    searcher_structure = es.get(index="structures_directory", id=labhalid)
    searcher_structure = searcher_structure["_source"]
    searcher_structure['idhal'] = idhal  # taggage, l'idhal sert de clé
    elastic_id = f"{idhal}.{searcher_structure['docid']}"
    es.index(index="sovisu_searchers", id=elastic_id, document=searcher_structure)
