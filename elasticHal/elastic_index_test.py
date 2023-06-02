import csv
import datetime
import json
import re

import dateutil.parser
from dateutil.relativedelta import relativedelta
from elasticsearch import helpers

from elasticHal.libs import (
    doi_enrichissement,
    elastic_formatting,
    hal,
    keyword_enrichissement,
    location_docs,
    utils, test_static,
)
from elasticHal.libs.archivesOuvertes import get_aurehalId, get_concepts_and_keywords
from sovisuhal.libs import esActions
from sovisuhal.viewsActions import idhal_checkout

es = esActions.es_connector()


def create_test_context():
    # Variables à automatiser plus tard
    idhal = "david-reymond"
    researcher_id = "dreymond"

    # remplissage index test_chercheur
    idhal_test = idhal_checkout(idhal)
    if idhal_test > 0:
        indexe_chercheur(idhal)

    # remplissage index test_laboratoire
    labo_message = get_labo_from_csv()
    print(labo_message)

    # remplissage index test_institution
    institution_message = get_institution_from_csv()
    print(institution_message)

    # remplissage index test_concepts
    concepts_message = get_expertises()
    print(concepts_message)

    # remplissage index test_publications
    scope_param = scope_p("_id", researcher_id)
    chercheur = es.search(index="test_researchers", query=scope_param)
    chercheur = chercheur["hits"]["hits"][0]["_source"]
    print(chercheur)

    publications_message = collecte_docs(chercheur)
    print(publications_message)

# TODO: Mettre à jour le format du document chercheur =>
#  créer un nested pour les labos qui contient structSirene, lab (=> laboratory acronym) et labhalid
def indexe_chercheur(idhal):  # self,
    """
    Indexe un chercheur dans Elasticsearch
    """
    """temp values:"""
    orcid = ""
    labo_accro = "IMSIC"
    idref = "test"
    labhalid = "527028"
    """end of temp values"""

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
    structid = "198307662"
    ldapid = "dreymond"

    # -----------------

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

    if len(nom) <= 0:
        nom = [""]
    elif len(emploi) <= 0:
        emploi = [""]
    elif len(mail) <= 0:
        mail = [""]

    # name,type,function,mail,lab,supannAffectation,supannEntiteAffectationPrincipale,halId_s,labHalId,idRef,structDomain,firstName,lastName,aurehalId
    chercheur = dict()
    # as-t-on besoin des 3 derniers champs ???
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

    chercheur["structSirene"] = structid
    chercheur["labHalId"] = labhalid
    chercheur["validated"] = False
    chercheur["ldapId"] = ldapid
    chercheur["Created"] = datetime.datetime.now().isoformat()

    # New step ?
    aurehal = ""
    archives_ouvertes_data = {}

    if idhal != "":
        aurehal = get_aurehalId(idhal)
        # integration contenus
        archives_ouvertes_data = get_concepts_and_keywords(aurehal)

    chercheur["halId_s"] = idhal
    chercheur["validated"] = False
    chercheur["aurehalId"] = aurehal  # heu ?
    chercheur["concepts"] = archives_ouvertes_data["concepts"] #TODO: voir pour intégrer le contenu par défaut dans SearcherProfile Validated_concepts. Le chercheur pourrait ensuit enlever les éléments si ça ne lui convient pas
    chercheur["guidingKeywords"] = []
    chercheur["idRef"] = idref
    chercheur["axis"] = labo_accro

    # add a category to make differentiation in text_* index pattern
    chercheur["category"] = "searcher"

    # add a common SearcherProfile Key who should serve has common key between index
    chercheur["SearcherProfile"] = [
        {"halId_s": chercheur["halId_s"],
         "ldapId": chercheur["ldapId"],
         "validated_concepts": []  # TODO: enlever ce champ et intégrer la validation directement dans l'index des concepts.
         }
    ]

    res = es.index(
        index="test_researchers",
        id=chercheur["ldapId"],
        document=json.dumps(chercheur),
        refresh="wait_for",
    )
    print("statut de la création d'index: ", res["result"])
    return ""


def get_labo_from_csv():
    laboratories_list = []
    scope_param = scope_all()
    count = es.count(index="test_laboratories", query=scope_param)["count"]
    print(count)
    res = es.search(index="test_laboratories", query=scope_param, size=count)
    res = res["hits"]["hits"]

    for results in res:
        laboratories_list.append(results["_source"])

    # Récupère les nouvelles données dans le csv
    with open("data/data_test/laboratories.csv", encoding="utf-8") as csv_file:
        laboratories_csv = list(csv.DictReader(csv_file, delimiter=";"))

        # vérifie si les labos dans la liste csv existent déjà dans kibana
        for laboratory in laboratories_csv:
            if not any(
                listed_lab["halStructId"] == laboratory["halStructId"]
                for listed_lab in laboratories_list
            ):
                # rajoute les labos non recensés aux existants
                laboratories_list.append(
                    elastic_formatting.laboratory_format(laboratory)
                )
            else:
                # Compare les données des labos existant dans les deux listes
                for listed_lab in laboratories_list:
                    if listed_lab["halStructId"] == laboratory["halStructId"]:
                        if laboratory["structSirene"] not in listed_lab["structSirene"]:
                            listed_lab["structSirene"].append(laboratory["structSirene"])

    helpers.bulk(es, laboratories_list, index="test_laboratories", refresh="wait_for")
    return "laboratories added"


def get_institution_from_csv(add_csv=True):
    institutions_list = []
    if add_csv:
        with open("data/data_test/structures.csv", encoding="utf-8") as csv_file:
            institution_csv = list(csv.DictReader(csv_file, delimiter=";"))

    for institution in institution_csv:
        # insert operations to make before append in the list for indexation
        institutions_list.append(elastic_formatting.institution_format(institution))

    helpers.bulk(es, institutions_list, index="test_institutions", refresh="wait_for")

    return "institutions added"


def get_expertises():
    concept_list = test_static.concepts()
    for row in concept_list:
        # add a category to make differentiation in text_* index pattern
        row["_id"] = row["id"]
        row["category"] = "expertise"

        for children in row["children"]:
            # nécessaire?
            children["category"] = "concept"

    helpers.bulk(es, concept_list, index="test_expertises", refresh="wait_for")

    return "concepts added"


def collecte_docs(chercheur, overwrite=False):  # self,
    """
    collecte_docs present dans elastichal.py
    partie Celery retirée pour les tests.
    Collecte les notices liées à un chercheur actuellement (peut être les labos également sous peu?)
    À mettre à jour et renommer lorsque intégré dans le code.
    Le code a été séparé en modules afin de pouvoir gérer les erreurs plus facilement
    """
    docs = hal.find_publications(chercheur["halId_s"], "authIdHal_s")

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

        document_exist = es.exists(index="test_publications", id=doc["_id"])

        # iterate for every searcher idhal present in doc
        for idhal in doc["authIdHal_s"]:
            validated_concepts = ""
            ldapId = "unassigned"
            validated = "unassigned"
            authorship = ""

            # check if the searcher with that idhal already exist in app
            searcher_param = {
                    "nested": {
                      "path": "SearcherProfile",
                      "query": {
                        "term": {
                          "SearcherProfile.halId_s.keyword": idhal
                        }
                      }
                    }
                }
            count_searcher = es.count(index="test_researchers", query=searcher_param)
            # TODO: Changer la méthode de vérification du chercheur,
            #  lorsque l'id commun passera sur l'idhal
            # searcher_exist = es.exists(index="test_researchers", id=idhal)

            # if searcher exist, get associated validated_concepts
            if count_searcher["count"] > 0:
                searcher_data = es.search(index="test_researchers", query=searcher_param)
                searcher_data = searcher_data["hits"]["hits"][0]["_source"]["SearcherProfile"][0]
                ldapId = searcher_data["ldapId"]
                validated_concepts = searcher_data["validated_concepts"]

            if overwrite or not document_exist:
                if count_searcher["count"] > 0:
                    validated = "True"
                # check authorship
                if doc["authIdHal_s"].index(idhal) == 0:
                    authorship = "firstAuthor"
                if doc["authIdHal_s"].index(idhal) == len(doc["authIdHal_s"]) - 1:
                    authorship = "lastAuthor"
            else:
                document_data = es.get(index="test_publications", id=doc["_id"])
                document_data = document_data["_source"]
                # Compare with datas already in document
                for searcher in document_data["SearcherProfile"]:
                    if searcher["halId_s"] == idhal:
                        if searcher["validated"] == "unassigned" and count_searcher["count"] > 0:
                            validated = "True"
                        else:
                            validated = searcher["validated"]
                        authorship = searcher["authorship"]

            # add the record of the Searcher in the document
            doc["SearcherProfile"].append(
                {
                    "halId_s": idhal,
                    "ldapId": ldapId,
                    "validated_concepts": validated_concepts,  # TODO: enlever ce champ et intégrer la validation directement dans l'index des concepts.
                    "validated": validated,
                    "authorship": authorship,
                }
            )

    helpers.bulk(es, docs, index="test_publications", refresh="wait_for")

    return "add publications done"


def should_be_open(notice):
    """
    Remplace should_be_open dans utils.py
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


# Elasticsearch queries
# the queries under are different from those already registered,
# and follow this deprecation worning: https://github.com/elastic/elasticsearch-py/issues/1698


def scope_p(scope_field, scope_value):
    """
    Retourne un ensemble de documents spécifique en fonction d'un filtre
    """
    scope = {"match": {scope_field: scope_value}}
    return scope


def scope_all():
    """
    Paramètre pour les requêtes ElasticSearch, retourne tous les documents
    """
    scope = {"match_all": {}}
    return scope


def laboratory_concepts(halStructId):
    rsr_param = scope_p("labHalId", halStructId)
    res = es.search(index="test_researchers", query=rsr_param)
    concept_tree = {"id": "Concepts", "children": []}
    for searcher in res["hits"]["hits"]:
        concept = searcher["_source"]["concepts"]

        if len(concept) > 0:
            for child in concept["children"]:
                if child["state"] == "invalidated":
                    concept_tree = utils.append_to_tree(
                        child, searcher["_source"], concept_tree, "invalidated"
                    )
                else:
                    concept_tree = utils.append_to_tree(
                        child, searcher["_source"], concept_tree, "validated"
                    )
                if "children" in child:
                    for child1 in child["children"]:
                        if child1["state"] == "invalidated":
                            concept_tree = utils.append_to_tree(
                                child1, searcher["_source"], concept_tree, "invalidated"
                            )
                        else:
                            concept_tree = utils.append_to_tree(
                                child1, searcher["_source"], concept_tree, "validated"
                            )

                        if "children" in child1:
                            for child2 in child1["children"]:
                                if child2["state"] == "invalidated":
                                    concept_tree = utils.append_to_tree(
                                        child2, searcher["_source"], concept_tree, "invalidated"
                                    )
                                else:
                                    concept_tree = utils.append_to_tree(
                                        child2, searcher["_source"], concept_tree, "validated"
                                    )
    return concept_tree


if __name__ == "__main__":
    if not es.ping():
        raise ValueError("Connection failed")

    index_mapping = {
        "researchers": elastic_formatting.searcher_mapping(),
        "publications": elastic_formatting.publication_mapping(),
        "laboratories": elastic_formatting.laboratories_mapping(),
        "institutions": elastic_formatting.institutions_mapping(),
        "expertises": elastic_formatting.expertises_mapping(),
    }

    for index, mapping_func in index_mapping.items():
        index_name = f"test_{index}"
        if not es.indices.exists(index=index_name):
            es.indices.create(index=index_name, mappings=mapping_func)

    create_test_context()
