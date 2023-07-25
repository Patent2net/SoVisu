# from libs import hal, utils, unpaywall, scanR
import datetime
import json
import re

import dateutil.parser
from celery import shared_task
from celery_progress.backend import ProgressRecorder
from dateutil.relativedelta import relativedelta
from decouple import config
from elasticsearch import helpers
from ldap3 import ALL, Connection, Server

from constants import SV_INDEX, TIMEZONE
# probablement le num établissement à terme
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
# TODO: Revoir la fonction pour débloquer la création de profils
def check_ldapid(ldapid):
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
                "displayName",  # A faire sauter
                "mail",
                "typeEmploi",
                "ustvstatus",
                "supannaffectation",
                "supanncodeentite",
                "supannEntiteAffectationPrincipale",
                "labo",  # A faire sauter
            ],
        )
        dico = json.loads(conn.response_to_json())["entries"][0]
    else:
        dico = {
            "attributes": {
                "labo": [],
                "mail": ["test@test.fr"],
                "supannAffectation": ["IMSIC", "IUT TC"],
                "supannEntiteAffectationPrincipale": "IUTTCO",
                "supanncodeentite": [],
                "typeEmploi": "Enseignant Chercheur Titulaire",
                "ustvStatus": ["OFFI"],
            },
            "dn": f"uid={ldapid},ou=Personnel,ou=people,dc=ldap-univ-tln,dc=fr",
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
    dico = check_ldapid(ldapid)

    # Get searcher data from HAL:
    searcher_data = hal.get_searcher_hal_data(idhal)

    # -----------------

    extrait = dico["dn"].split("uid=")[1].split(",")
    chercheur_type = extrait[1].replace("ou=", "")
    suppan_id = extrait[0]
    if suppan_id != ldapid:
        print("aille", ldapid, " --> ", ldapid)

    emploi = dico["attributes"]["typeEmploi"] if len(dico["attributes"]["typeEmploi"]) > 0 else [
        ""]  # TODO: Revoir
    mail = dico["attributes"]["mail"] if len(dico["attributes"]["mail"]) > 0 else [
        ""]  # TODO: revoir

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
    # TODO: continuer à ajuster pour fonctionner le plus possible avec searcher_data
    searcher_notice = {
        "name": searcher_data["fullName_s"],
        "type": chercheur_type,
        "function": emploi,
        "mail": mail[0],  # TODO: Intéret?
        "orcId": orcid,
        "lab": labo_accro,  # TODO: INTERET DE CETTE KEY?
        "supannAffectation": ";".join(supann_affect),
        # TODO: faire sauter pour créer un document structure à la place?
        "supannEntiteAffectationPrincipale": supann_princ,
        # TODO: faire sauter pour créer un document structure à la place?
        "firstName": searcher_data["firstName_s"],
        "lastName": searcher_data["lastName_s"],
        "structSirene": structid,
        "labHalId": labhalid,
        "validated": False,
        "ldapId": ldapid,
        "Created": datetime.datetime.now(tz=TIMEZONE).isoformat(),
        "idhal": idhal,
        # sert de clé pivot entre les docs, il faut être sûr que ce champ n'existe dans aucune des docs que l'on pourrait indexer
        "halId_s": idhal,
        "aurehalId": aurehal,
        "idRef": idref,
        "axis": labo_accro,  # TODO: INTERET DE CETTE KEY? contient la même chose que lab
        "sovisu_category": "searcher"
    }

    res = es.index(
        index=SV_INDEX,
        id=idhal,
        document=searcher_notice,
        refresh="wait_for",
    )

    # integration contenus
    create_searcher_concept_notices(idhal, aurehal)
    create_searcher_structure_notices(idhal, labhalid)
    print("statut de la création d'index: ", res["result"])


@shared_task(bind=True)
def collecte_docs(self, entite):  # self,
    """
    collecte_docs present dans elastichal.py
    partie Celery retirée pour les tests.
    Collecte les notices liées à un chercheur actuellement (peut être les labos également sous peu?)
    À mettre à jour et renommer lorsque intégré dans le code.
    Le code a été séparé en modules afin de pouvoir gérer les erreurs plus facilement
    """
    doc_progress_recorder = ProgressRecorder(self)
    new_documents = []

    # look hal.find_publication for full base list of keys.
    if entite["sovisu_category"] == 'searcher':
        idhal = entite["idhal"]
        docs = hal.find_publications(idhal, "authIdHal_s")

    else:
        idhal = entite["idhal"]
        docs = hal.find_publications(idhal, "labStructId_i")
    for num, doc in enumerate(docs):
        # Check if the document already exist in elastic for the searcher.
        # If yes, it update values depending if the mds changed or not and then es.updated
        # if not, it create the document, append it to new_documents and then helpers.bulk
        changements = False
        elastic_doc_id = f"{idhal}.{doc['halId_s']}"
        document_exist = es.exists(index=SV_INDEX, id=elastic_doc_id)
        if document_exist:
            existing_document = es.get(index=SV_INDEX, id=elastic_doc_id)
            existing_document = existing_document["_source"]

            doc["MDS"] = utils.calculate_mds(doc)

            if doc["MDS"] != existing_document["MDS"]:
                # SI le MDS a changé alors modif qualitative sur la notice
                changements = True
            else:
                doc = existing_document

        else:
            doc["records"] = []
            doc["sovisu_category"] = "notice"
            doc["sovisu_referentiel"] = "hal"
            doc["idhal"] = idhal,  # l'Astuce du
            doc["sovisu_id"] = f'{idhal}.{doc["halId_s"]}'
            doc["sovisu_validated"] = True

            # Calcul de l'autorat du chercheur
            if entite["sovisu_category"] == 'searcher':
                authorship = ""
                # TODO: Revoir pour être plus fiable?
                if doc["authIdHal_s"].index(idhal) == 0:
                    authorship = "firstAuthor"
                if doc["authIdHal_s"].index(idhal) == len(doc["authIdHal_s"]) - 1:
                    authorship = "lastAuthor"

                doc["sovisu_authorship"] = authorship

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
            doc["Created"] = datetime.datetime.now(tz=TIMEZONE).isoformat()

        # on recalcule à chaque collecte... pour màj
        doc["postprint_embargo"], doc["preprint_embargo"] = should_be_open(doc)

        if document_exist:
            es.update(index=SV_INDEX, id=elastic_doc_id, doc=doc, refresh="wait_for")
        else:
            doc["_id"] = elastic_doc_id
            new_documents.append(doc)
        doc_progress_recorder.set_progress(num, len(docs),
                                           str(num) + " sur " + str(len(docs)) + " documents")

    for indi in range(int(len(new_documents) // 50) + 1):
        boutdeDoc = new_documents[indi * 50: indi * 50 + 50]
        helpers.bulk(
            es,
            boutdeDoc,
            index=SV_INDEX,
        )

    doc_progress_recorder.set_progress(num, len(docs),
                                       str(num) + " sur " + str(len(docs)) + " indexés")
    return "add publications done"


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

                        curr_date = datetime.datetime.now(tz=TIMEZONE).date()
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


def creeFichesExpertise(idx, idHal, aureHal, lstDom):
    # AUCUN des deux scope ne remontent toutes les fiches domaine chercheur : elles n'existent pas. GRRRR
    query = esActions.scope_all()
    count = es.count(index="domaine_hal_referentiel", query=query)["count"]
    # récup du référentiel
    toutRef = [truc['_source']['chemin'] for truc in
               es.search(index="domaine_hal_referentiel", query={'match_all': {}}, size=count)[
                   'hits']['hits']]

    Vu = set()
    pasVu = set()
    # Traitement des nouveaux
    for ids in list(set(lstDom)):
        ok = False
        for ch in toutRef:
            if ch.endswith(ids):
                Vu.add(ch)
                ok = True
        if not ok:
            pasVu.add(ids)
    ####
    # Traitement des vus... matchés on recopie la fiche référentiel et on personnalise. Actuellement, on taggue

    for new in pasVu:
        # ces domaines ou sous domaines ne sont pas dans https://api.archives-ouvertes.fr/ref/domain/?q=*&wt=json&fl=*
        # on créé les entrées ici et on marque le problème du référentiel dans le champ refOk
        domaine = dict()
        domaine["id"] = new
        domaine["label_fr"] = new
        domaine["label_en"] = new
        newFiche = utils.creeFiche(domaine)
        newFiche['idhal'] = idHal
        newFiche['aurehal'] = aureHal
        newFiche['validated'] = False
        elastic_id = f"{idHal}.{newFiche['chemin']}"
        newFiche['sovisu_id'] = elastic_id
        newFiche['refOk'] = False
        newFiche['level'] = newFiche['chemin'].count(
            '.')  # champ pour affichage... pas trouvé mieux
        newFiche['origin'] = "datagouv"
        # print("Nouveau dans le dico ??? çà sort d'où ?", new)
        es.index(index=idx, id=elastic_id, document=json.dumps(newFiche), refresh="wait_for", )

    # Ci dessous peut être grandement simplifié
    # il suffit de trouver la requête sur es qui donne un match exact (sur le champ chemin) pour tous les Vu
    for dom in Vu:
        lstReq = [{
            "match": {
                "chemin": dom
            }
        }]

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
            if fiche['_source'][
                'chemin'] == dom:  # si la req pouvait donner un match exact, on se passerait de çà
                newFiche = fiche['_source']
                newFiche['validated'] = False  # domaines pas validés par défaut
                # Id proposition : valider les domaines par défaut et laisser la possibilité d'en valider d'autres par explorateur d'arbre ?
                newFiche['idhal'] = idHal  # taggage, l'idhal sert de clé
                newFiche['aurehal'] = aureHal  # un domaine est attaché à l'aurehalId
                # Et rajouts besoins spécifiques (genre précisions / notes...)
                elastic_id = f"{idHal}.{newFiche['chemin']}"
                newFiche['sovisu_id'] = elastic_id
                newFiche['level'] = dom.count('.')  # champ pour affichage... pas trouvé mieux
                newFiche['refOk'] = True  # champ pour désigner les pb du référentiel
                # Puis on indexe la fiche
                newFiche['origin'] = "datagouv"
                es.index(index=idx, id=elastic_id, document=json.dumps(newFiche),
                         refresh="wait_for", )


# TODO: Refactor that function
def create_searcher_concept_notices(idhal, aurehal):
    archives_ouvertes_data = get_concepts_and_keywords(aurehal)
    # Gestion des existants
    chercheur_concept = archives_ouvertes_data["concepts"]
    query = {
        "bool": {
            "must": [
                {"match": {"sovisu_category": "expertise"}},
                {"match": {"idhal": idhal}},
            ]
        }
    }
    expertises_count = es.count(index=SV_INDEX, query=query)["count"]
    searcher_expertises = es.search(index=SV_INDEX, query=query,
                                    size=expertises_count)
    searcher_expertises = searcher_expertises["hits"]["hits"]

    if len(chercheur_concept) > 0:

        idDomainChecheur = []
        for concept1 in chercheur_concept['children']:
            idDomainChecheur.append(concept1['id'])
            if 'children' in concept1.keys():
                for concept2 in concept1['children']:
                    idDomainChecheur.append(concept2['id'])
                    if 'children' in concept2.keys():  # pas sûr du besoin de ce niveau là
                        for concept3 in concept2['children']:
                            idDomainChecheur.append(concept3['id'])
        # idDomainChecheur = [exp['id'] for exp in chercheur_concept['children']]

        # Gestion des existants
        dejaLa = [fiche for fiche in searcher_expertises if
                  fiche["_source"]['chemin'].replace("domAurehal.", "") in idDomainChecheur]

        for fiche in dejaLa:
            if fiche["_source"]['origin'] != "datagouv":
                fiche["_source"]['origin'] = "datagouv"
                # fiche["_source"]['validated'] = True
                es.update(index=SV_INDEX, id=fiche["_id"], body=fiche["_source"])
            idDomainChecheur.remove(fiche["_source"]['chemin'].replace("domAurehal.", ""))
        # les autres on les créé
        creeFichesExpertise(idx=SV_INDEX, idHal=idhal, aureHal=aurehal, lstDom=idDomainChecheur)


def create_searcher_structure_notices(idhal, labhalid):
    searcher_structure = es.get(index="structures_directory", id=labhalid)
    searcher_structure = searcher_structure["_source"]
    searcher_structure['idhal'] = idhal  # taggage, l'idhal sert de clé
    elastic_id = f"{idhal}.{searcher_structure['docid']}"
    es.index(index=SV_INDEX, id=elastic_id, document=searcher_structure)
