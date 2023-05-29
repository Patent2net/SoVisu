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
    utils,
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
    chercheur["concepts"] = archives_ouvertes_data["concepts"]
    chercheur["guidingKeywords"] = []
    chercheur["idRef"] = idref
    chercheur["axis"] = labo_accro

    # add a category to make differentiation in text_* index pattern
    chercheur["category"] = "searcher"

    # add a common SearcherProfile Key who should serve has common key between index
    chercheur["SearcherProfile"] = [
        {"halId_s": chercheur["halId_s"], "ldapId": chercheur["ldapId"], "validated_concepts": []}
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
    with open("data/laboratories.csv", encoding="utf-8") as csv_file:
        laboratories_csv = list(csv.DictReader(csv_file, delimiter=";"))

        # vérifie si les labos dans la liste csv existent déjà dans kibana
        for laboratory in laboratories_csv:
            if not any(
                listed_lab["halStructId"] == laboratory["halStructId"]
                for listed_lab in laboratories_list
            ):
                # rajoute les labos non recensés aux existants
                concept_tree = laboratory_concepts(laboratory["halStructId"])

                laboratories_list.append(
                    elastic_formatting.laboratory_format(laboratory, concept_tree)
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
        with open("data/structures.csv", encoding="utf-8") as csv_file:
            institution_csv = list(csv.DictReader(csv_file, delimiter=";"))

    for institution in institution_csv:
        # insert operations to make before append in the list for indexation
        institutions_list.append(elastic_formatting.institution_format(institution))

    helpers.bulk(es, institutions_list, index="test_institutions", refresh="wait_for")

    return "institutions added"


def get_expertises():
    concept_list = concepts()
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
                    "validated_concepts": validated_concepts,
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


def concepts():
    """
    Retourne la liste des concepts pouvant être par la suite assignés à un chercheur
    version modifiée, version initiale dans halConcepts.py
    Modifier la version initiale si le contenu du fichier test est validé
    """
    return [
        {
            "id": "chim",
            "label_en": "Chemical Sciences",
            "label_fr": "Chimie",
            "children": [
                {
                    "id": "chim.anal",
                    "label_en": "Analytical chemistry",
                    "label_fr": "Chimie analytique",
                    "children": [],
                },
                {
                    "id": "chim.cata",
                    "label_en": "Catalysis",
                    "label_fr": "Catalyse",
                    "children": [],
                },
                {
                    "id": "chim.chem",
                    "label_en": "Cheminformatics",
                    "label_fr": "Chemo-informatique",
                    "children": [],
                },
                {
                    "id": "chim.coor",
                    "label_en": "Coordination chemistry",
                    "label_fr": "Chimie de coordination",
                    "children": [],
                },
                {
                    "id": "chim.cris",
                    "label_en": "Cristallography",
                    "label_fr": "Cristallographie",
                    "children": [],
                },
                {
                    "id": "chim.geni",
                    "label_en": "Chemical engineering",
                    "label_fr": "Génie chimique",
                    "children": [],
                },
                {
                    "id": "chim.inor",
                    "label_en": "Inorganic chemistry",
                    "label_fr": "Chimie inorganique",
                    "children": [],
                },
                {
                    "id": "chim.mate",
                    "label_en": "Material chemistry",
                    "label_fr": "Matériaux",
                    "children": [],
                },
                {
                    "id": "chim.orga",
                    "label_en": "Organic chemistry",
                    "label_fr": "Chimie organique",
                    "children": [],
                },
                {
                    "id": "chim.othe",
                    "label_en": "Other",
                    "label_fr": "Autre",
                    "children": [],
                },
                {
                    "id": "chim.poly",
                    "label_en": "Polymers",
                    "label_fr": "Polymères",
                    "children": [],
                },
                {
                    "id": "chim.radio",
                    "label_en": "Radiochemistry",
                    "label_fr": "Radiochimie",
                    "children": [],
                },
                {
                    "id": "chim.theo",
                    "label_en": "Theoretical and/or physical chemistry",
                    "label_fr": "Chimie théorique et/ou physique",
                    "children": [],
                },
                {
                    "id": "chim.ther",
                    "label_en": "Medicinal Chemistry",
                    "label_fr": "Chimie thérapeutique",
                    "children": [],
                },
            ],
        },
        {
            "id": "info",
            "label_en": "Computer Science",
            "label_fr": "Informatique",
            "children": [
                {
                    "id": "info.eiah",
                    "label_en": "Technology for Human Learning",
                    "label_fr": "Environnements Informatiques pour l'Apprentissage Humain",
                    "children": [],
                },
                {
                    "id": "info.info-ai",
                    "label_en": "Artificial Intelligence",
                    "label_fr": "Intelligence artificielle",
                    "children": [],
                },
                {
                    "id": "info.info-ao",
                    "label_en": "Computer Arithmetic",
                    "label_fr": "Arithmétique des ordinateurs",
                    "children": [],
                },
                {
                    "id": "info.info-ar",
                    "label_en": "Hardware Architecture",
                    "label_fr": "Architectures Matérielles",
                    "children": [],
                },
                {
                    "id": "info.info-au",
                    "label_en": "Automatic Control Engineering",
                    "label_fr": "Automatique",
                    "children": [],
                },
                {
                    "id": "info.info-bi",
                    "label_en": "Bioinformatics",
                    "label_fr": "Bio-informatique",
                    "children": [],
                },
                {
                    "id": "info.info-bt",
                    "label_en": "Biotechnology",
                    "label_fr": "Biotechnologie",
                    "children": [],
                },
                {
                    "id": "info.info-cc",
                    "label_en": "Computational Complexity",
                    "label_fr": "Complexité",
                    "children": [],
                },
                {
                    "id": "info.info-ce",
                    "label_en": "Computational Engineering, Finance, and Science",
                    "label_fr": "Ingénierie, finance et science",
                    "children": [],
                },
                {
                    "id": "info.info-cg",
                    "label_en": "Computational Geometry",
                    "label_fr": "Géométrie algorithmique",
                    "children": [],
                },
                {
                    "id": "info.info-cl",
                    "label_en": "Computation and Language",
                    "label_fr": "Informatique et langage",
                    "children": [],
                },
                {
                    "id": "info.info-cr",
                    "label_en": "Cryptography and Security",
                    "label_fr": "Cryptographie et sécurité",
                    "children": [],
                },
                {
                    "id": "info.info-cv",
                    "label_en": "Computer Vision and Pattern Recognition",
                    "label_fr": "Vision par ordinateur et reconnaissance de formes",
                    "children": [],
                },
                {
                    "id": "info.info-cy",
                    "label_en": "Computers and Society",
                    "label_fr": "Ordinateur et société",
                    "children": [],
                },
                {
                    "id": "info.info-db",
                    "label_en": "Databases",
                    "label_fr": "Base de données",
                    "children": [],
                },
                {
                    "id": "info.info-dc",
                    "label_en": "Distributed, Parallel, and Cluster Computing",
                    "label_fr": "Calcul parallèle, distribué et partagé",
                    "children": [],
                },
                {
                    "id": "info.info-dl",
                    "label_en": "Digital Libraries",
                    "label_fr": "Bibliothèque électronique",
                    "children": [],
                },
                {
                    "id": "info.info-dm",
                    "label_en": "Discrete Mathematics",
                    "label_fr": "Mathématique discrète",
                    "children": [],
                },
                {
                    "id": "info.info-ds",
                    "label_en": "Data Structures and Algorithms",
                    "label_fr": "Algorithme et structure de données",
                    "children": [],
                },
                {
                    "id": "info.info-es",
                    "label_en": "Embedded Systems",
                    "label_fr": "Systèmes embarqués",
                    "children": [],
                },
                {
                    "id": "info.info-gl",
                    "label_en": "General Literature",
                    "label_fr": "Littérature générale",
                    "children": [],
                },
                {
                    "id": "info.info-gr",
                    "label_en": "Graphics",
                    "label_fr": "Synthèse d'image et réalité virtuelle",
                    "children": [],
                },
                {
                    "id": "info.info-gt",
                    "label_en": "Computer Science and Game Theory",
                    "label_fr": "Informatique et théorie des jeux",
                    "children": [],
                },
                {
                    "id": "info.info-hc",
                    "label_en": "Human-Computer Interaction",
                    "label_fr": "Interface homme-machine",
                    "children": [],
                },
                {
                    "id": "info.info-ia",
                    "label_en": "Computer Aided Engineering",
                    "label_fr": "Ingénierie assistée par ordinateur",
                    "children": [],
                },
                {
                    "id": "info.info-im",
                    "label_en": "Medical Imaging",
                    "label_fr": "Imagerie médicale",
                    "children": [],
                },
                {
                    "id": "info.info-ir",
                    "label_en": "Information Retrieval",
                    "label_fr": "Recherche d'information",
                    "children": [],
                },
                {
                    "id": "info.info-it",
                    "label_en": "Information Theory",
                    "label_fr": "Théorie de l'information",
                    "children": [],
                },
                {
                    "id": "info.info-iu",
                    "label_en": "Ubiquitous Computing",
                    "label_fr": "Informatique ubiquitaire",
                    "children": [],
                },
                {
                    "id": "info.info-lg",
                    "label_en": "Machine Learning",
                    "label_fr": "Apprentissage",
                    "children": [],
                },
                {
                    "id": "info.info-lo",
                    "label_en": "Logic in Computer Science",
                    "label_fr": "Logique en informatique",
                    "children": [],
                },
                {
                    "id": "info.info-ma",
                    "label_en": "Multiagent Systems",
                    "label_fr": "Système multi-agents",
                    "children": [],
                },
                {
                    "id": "info.info-mc",
                    "label_en": "Mobile Computing",
                    "label_fr": "Informatique mobile",
                    "children": [],
                },
                {
                    "id": "info.info-mm",
                    "label_en": "Multimedia",
                    "label_fr": "Multimédia",
                    "children": [],
                },
                {
                    "id": "info.info-mo",
                    "label_en": "Modeling and Simulation",
                    "label_fr": "Modélisation et simulation",
                    "children": [],
                },
                {
                    "id": "info.info-ms",
                    "label_en": "Mathematical Software",
                    "label_fr": "Logiciel mathématique",
                    "children": [],
                },
                {
                    "id": "info.info-na",
                    "label_en": "Numerical Analysis",
                    "label_fr": "Analyse numérique",
                    "children": [],
                },
                {
                    "id": "info.info-ne",
                    "label_en": "Neural and Evolutionary Computing",
                    "label_fr": "Réseau de neurones",
                    "children": [],
                },
                {
                    "id": "info.info-ni",
                    "label_en": "Networking and Internet Architecture",
                    "label_fr": "Réseaux et télécommunications",
                    "children": [],
                },
                {
                    "id": "info.info-oh",
                    "label_en": "Other",
                    "label_fr": "Autre",
                    "children": [],
                },
                {
                    "id": "info.info-os",
                    "label_en": "Operating Systems",
                    "label_fr": "Système d'exploitation",
                    "children": [],
                },
                {
                    "id": "info.info-pf",
                    "label_en": "Performance",
                    "label_fr": "Performance et fiabilité",
                    "children": [],
                },
                {
                    "id": "info.info-et",
                    "label_en": "Emerging Technologies",
                    "label_fr": "Technologies Émergeantes",
                    "children": [],
                },
                {
                    "id": "info.info-pl",
                    "label_en": "Programming Languages",
                    "label_fr": "Langage de programmation",
                    "children": [],
                },
                {
                    "id": "info.info-rb",
                    "label_en": "Robotics",
                    "label_fr": "Robotique",
                    "children": [],
                },
                {
                    "id": "info.info-ro",
                    "label_en": "Operations Research",
                    "label_fr": "Recherche opérationnelle",
                    "children": [],
                },
                {
                    "id": "info.info-sc",
                    "label_en": "Symbolic Computation",
                    "label_fr": "Calcul formel",
                    "children": [],
                },
                {
                    "id": "info.info-sd",
                    "label_en": "Sound",
                    "label_fr": "Son",
                    "children": [],
                },
                {
                    "id": "info.info-se",
                    "label_en": "Software Engineering",
                    "label_fr": "Génie logiciel",
                    "children": [],
                },
                {
                    "id": "info.info-ti",
                    "label_en": "Image Processing",
                    "label_fr": "Traitement des images",
                    "children": [],
                },
                {
                    "id": "info.info-ts",
                    "label_en": "Signal and Image Processing",
                    "label_fr": "Traitement du signal et de l'image",
                    "children": [],
                },
                {
                    "id": "info.info-tt",
                    "label_en": "Document and Text Processing",
                    "label_fr": "Traitement du texte et du document",
                    "children": [],
                },
                {
                    "id": "info.info-wb",
                    "label_en": "Web",
                    "label_fr": "Web",
                    "children": [],
                },
                {
                    "id": "info.info-fl",
                    "label_en": "Formal Languages and Automata Theory",
                    "label_fr": "Théorie et langage formel",
                    "children": [],
                },
                {
                    "id": "info.info-si",
                    "label_en": "Social and Information Networks",
                    "label_fr": "Réseaux sociaux et d'information",
                    "children": [],
                },
                {
                    "id": "info.info-sy",
                    "label_en": "Systems and Control",
                    "label_fr": "Systèmes et contrôle",
                    "children": [],
                },
            ],
        },
        {
            "id": "math",
            "label_en": "Mathematics",
            "label_fr": "Mathématiques",
            "children": [
                {
                    "id": "math.math-ac",
                    "label_en": "Commutative Algebra",
                    "label_fr": "Algèbre commutative",
                    "children": [],
                },
                {
                    "id": "math.math-ag",
                    "label_en": "Algebraic Geometry",
                    "label_fr": "Géométrie algébrique",
                    "children": [],
                },
                {
                    "id": "math.math-ap",
                    "label_en": "Analysis of PDEs",
                    "label_fr": "Equations aux dérivées partielles",
                    "children": [],
                },
                {
                    "id": "math.math-at",
                    "label_en": "Algebraic Topology",
                    "label_fr": "Topologie algébrique",
                    "children": [],
                },
                {
                    "id": "math.math-ca",
                    "label_en": "Classical Analysis and ODEs",
                    "label_fr": "Analyse classique",
                    "children": [],
                },
                {
                    "id": "math.math-co",
                    "label_en": "Combinatorics",
                    "label_fr": "Combinatoire",
                    "children": [],
                },
                {
                    "id": "math.math-ct",
                    "label_en": "Category Theory",
                    "label_fr": "Catégories et ensembles",
                    "children": [],
                },
                {
                    "id": "math.math-cv",
                    "label_en": "Complex Variables",
                    "label_fr": "Variables complexes",
                    "children": [],
                },
                {
                    "id": "math.math-dg",
                    "label_en": "Differential Geometry",
                    "label_fr": "Géométrie différentielle",
                    "children": [],
                },
                {
                    "id": "math.math-ds",
                    "label_en": "Dynamical Systems",
                    "label_fr": "Systèmes dynamiques",
                    "children": [],
                },
                {
                    "id": "math.math-fa",
                    "label_en": "Functional Analysis",
                    "label_fr": "Analyse fonctionnelle",
                    "children": [],
                },
                {
                    "id": "math.math-gm",
                    "label_en": "General Mathematics",
                    "label_fr": "Mathématiques générales",
                    "children": [],
                },
                {
                    "id": "math.math-gn",
                    "label_en": "General Topology",
                    "label_fr": "Topologie générale",
                    "children": [],
                },
                {
                    "id": "math.math-gr",
                    "label_en": "Group Theory",
                    "label_fr": "Théorie des groupes",
                    "children": [],
                },
                {
                    "id": "math.math-gt",
                    "label_en": "Geometric Topology",
                    "label_fr": "Topologie géométrique",
                    "children": [],
                },
                {
                    "id": "math.math-ho",
                    "label_en": "History and Overview",
                    "label_fr": "Histoire et perspectives sur les mathématiques",
                    "children": [],
                },
                {
                    "id": "math.math-it",
                    "label_en": "Information Theory",
                    "label_fr": "Théorie de l'information et codage",
                    "children": [],
                },
                {
                    "id": "math.math-kt",
                    "label_en": "K-Theory and Homology",
                    "label_fr": "K-théorie et homologie",
                    "children": [],
                },
                {
                    "id": "math.math-lo",
                    "label_en": "Logic",
                    "label_fr": "Logique",
                    "children": [],
                },
                {
                    "id": "math.math-mg",
                    "label_en": "Metric Geometry",
                    "label_fr": "Géométrie métrique",
                    "children": [],
                },
                {
                    "id": "math.math-mp",
                    "label_en": "Mathematical Physics",
                    "label_fr": "Physique mathématique",
                    "children": [],
                },
                {
                    "id": "math.math-na",
                    "label_en": "Numerical Analysis",
                    "label_fr": "Analyse numérique",
                    "children": [],
                },
                {
                    "id": "math.math-nt",
                    "label_en": "Number Theory",
                    "label_fr": "Théorie des nombres",
                    "children": [],
                },
                {
                    "id": "math.math-oa",
                    "label_en": "Operator Algebras",
                    "label_fr": "Algèbres d'opérateurs",
                    "children": [],
                },
                {
                    "id": "math.math-oc",
                    "label_en": "Optimization and Control",
                    "label_fr": "Optimisation et contrôle",
                    "children": [],
                },
                {
                    "id": "math.math-pr",
                    "label_en": "Probability",
                    "label_fr": "Probabilités",
                    "children": [],
                },
                {
                    "id": "math.math-qa",
                    "label_en": "Quantum Algebra",
                    "label_fr": "Algèbres quantiques",
                    "children": [],
                },
                {
                    "id": "math.math-ra",
                    "label_en": "Rings and Algebras",
                    "label_fr": "Anneaux et algèbres",
                    "children": [],
                },
                {
                    "id": "math.math-rt",
                    "label_en": "Representation Theory",
                    "label_fr": "Théorie des représentations",
                    "children": [],
                },
                {
                    "id": "math.math-sg",
                    "label_en": "Symplectic Geometry",
                    "label_fr": "Géométrie symplectique",
                    "children": [],
                },
                {
                    "id": "math.math-sp",
                    "label_en": "Spectral Theory",
                    "label_fr": "Théorie spectrale",
                    "children": [],
                },
                {
                    "id": "math.math-st",
                    "label_en": "Statistics",
                    "label_fr": "Statistiques",
                    "children": [],
                },
            ],
        },
        {
            "id": "nlin",
            "label_en": "Nonlinear Sciences",
            "label_fr": "Science non linéaire",
            "children": [
                {
                    "id": "nlin.nlin-ao",
                    "label_en": "Adaptation and Self-Organizing Systems",
                    "label_fr": "Adaptation et Systèmes auto-organisés",
                    "children": [],
                },
                {
                    "id": "nlin.nlin-cd",
                    "label_en": "Chaotic Dynamics",
                    "label_fr": "Dynamique Chaotique",
                    "children": [],
                },
                {
                    "id": "nlin.nlin-cg",
                    "label_en": "Cellular Automata and Lattice Gases",
                    "label_fr": "Automates cellulaires et gaz sur réseau",
                    "children": [],
                },
                {
                    "id": "nlin.nlin-ps",
                    "label_en": "Pattern Formation and Solitons",
                    "label_fr": "Formation de Structures et Solitons",
                    "children": [],
                },
                {
                    "id": "nlin.nlin-si",
                    "label_en": "Exactly Solvable and Integrable Systems",
                    "label_fr": "Systèmes Solubles et Intégrables",
                    "children": [],
                },
            ],
        },
        {
            "id": "phys",
            "label_en": "Physics",
            "label_fr": "Physique",
            "children": [
                {
                    "id": "phys.astr",
                    "label_en": "Astrophysics",
                    "label_fr": "Astrophysique",
                    "children": [
                        {
                            "id": "phys.astr.co",
                            "label_en": "Cosmology and Extra-Galactic Astrophysics",
                            "label_fr": "Cosmologie et astrophysique extra-galactique",
                            "children": [],
                        },
                        {
                            "id": "phys.astr.ep",
                            "label_en": "Earth and Planetary Astrophysics",
                            "label_fr": "Planétologie et astrophysique de la terre",
                            "children": [],
                        },
                        {
                            "id": "phys.astr.ga",
                            "label_en": "Galactic Astrophysics",
                            "label_fr": "Astrophysique galactique",
                            "children": [],
                        },
                        {
                            "id": "phys.astr.he",
                            "label_en": "High Energy Astrophysical Phenomena",
                            "label_fr": "Phénomènes cosmiques de haute energie",
                            "children": [],
                        },
                        {
                            "id": "phys.astr.im",
                            "label_en": "Instrumentation and Methods for Astrophysic",
                            "label_fr": "Instrumentation et méthodes pour l'astrophysique",
                            "children": [],
                        },
                        {
                            "id": "phys.astr.sr",
                            "label_en": "Solar and Stellar Astrophysics",
                            "label_fr": "Astrophysique stellaire et solaire",
                            "children": [],
                        },
                    ],
                },
                {
                    "id": "phys.cond",
                    "label_en": "Condensed Matter",
                    "label_fr": "Matière Condensée",
                    "children": [
                        {
                            "id": "phys.cond.cm-ds-nn",
                            "label_en": "Disordered Systems and Neural Networks",
                            "label_fr": "Systèmes désordonnés et réseaux de neurones",
                            "children": [],
                        },
                        {
                            "id": "phys.cond.cm-gen",
                            "label_en": "Other",
                            "label_fr": "Autre",
                            "children": [],
                        },
                        {
                            "id": "phys.cond.cm-ms",
                            "label_en": "Materials Science",
                            "label_fr": "Science des matériaux",
                            "children": [],
                        },
                        {
                            "id": "phys.cond.cm-msqhe",
                            "label_en": "Mesoscopic Systems and Quantum Hall Effect",
                            "label_fr": "Systèmes mésoscopiques et effet Hall quantique",
                            "children": [],
                        },
                        {
                            "id": "phys.cond.cm-s",
                            "label_en": "Superconductivity",
                            "label_fr": "Supraconductivité",
                            "children": [],
                        },
                        {
                            "id": "phys.cond.cm-sce",
                            "label_en": "Strongly Correlated Electrons",
                            "label_fr": "Electrons fortement corrélés",
                            "children": [],
                        },
                        {
                            "id": "phys.cond.cm-scm",
                            "label_en": "Soft Condensed Matter",
                            "label_fr": "Matière Molle",
                            "children": [],
                        },
                        {
                            "id": "phys.cond.cm-sm",
                            "label_en": "Statistical Mechanics",
                            "label_fr": "Mécanique statistique",
                            "children": [],
                        },
                        {
                            "id": "phys.cond.gas",
                            "label_en": "Quantum Gases",
                            "label_fr": "Gaz Quantiques",
                            "children": [],
                        },
                    ],
                },
                {
                    "id": "phys.grqc",
                    "label_en": "General Relativity and Quantum Cosmology",
                    "label_fr": "Relativité Générale et Cosmologie Quantique",
                    "children": [],
                },
                {
                    "id": "phys.hexp",
                    "label_en": "High Energy Physics - Experiment",
                    "label_fr": "Physique des Hautes Energies - Expérience",
                    "children": [],
                },
                {
                    "id": "phys.hlat",
                    "label_en": "High Energy Physics - Lattice",
                    "label_fr": "Physique des Hautes Energies - Réseau",
                    "children": [],
                },
                {
                    "id": "phys.hphe",
                    "label_en": "High Energy Physics - Phenomenology",
                    "label_fr": "Physique des Hautes Energies - Phénoménologie",
                    "children": [],
                },
                {
                    "id": "phys.hthe",
                    "label_en": "High Energy Physics - Theory",
                    "label_fr": "Physique des Hautes Energies - Théorie",
                    "children": [],
                },
                {
                    "id": "phys.meca",
                    "label_en": "Mechanics",
                    "label_fr": "Mécanique",
                    "children": [
                        {
                            "id": "phys.meca.acou",
                            "label_en": "Acoustics",
                            "label_fr": "Acoustique",
                            "children": [],
                        },
                        {
                            "id": "phys.meca.biom",
                            "label_en": "Biomechanics",
                            "label_fr": "Biomécanique",
                            "children": [],
                        },
                        {
                            "id": "phys.meca.geme",
                            "label_en": "Mechanical engineering",
                            "label_fr": "Génie mécanique",
                            "children": [],
                        },
                        {
                            "id": "phys.meca.mefl",
                            "label_en": "Mechanics of the fluids",
                            "label_fr": "Mécanique des fluides",
                            "children": [],
                        },
                        {
                            "id": "phys.meca.mema",
                            "label_en": "Mechanics of materials",
                            "label_fr": "Mécanique des matériaux",
                            "children": [],
                        },
                        {
                            "id": "phys.meca.msmeca",
                            "label_en": "Materials and structures in mechanics",
                            "label_fr": "Matériaux et structures en mécanique",
                            "children": [],
                        },
                        {
                            "id": "phys.meca.solid",
                            "label_en": "Mechanics of the solides",
                            "label_fr": "Mécanique des solides",
                            "children": [],
                        },
                        {
                            "id": "phys.meca.stru",
                            "label_en": "Mechanics of the structures",
                            "label_fr": "Mécanique des structures",
                            "children": [],
                        },
                        {
                            "id": "phys.meca.ther",
                            "label_en": "Thermics",
                            "label_fr": "Thermique",
                            "children": [],
                        },
                        {
                            "id": "phys.meca.vibr",
                            "label_en": "Vibrations",
                            "label_fr": "Vibrations",
                            "children": [],
                        },
                    ],
                },
                {
                    "id": "phys.mphy",
                    "label_en": "Mathematical Physics",
                    "label_fr": "Physique mathématique",
                    "children": [],
                },
                {
                    "id": "phys.nexp",
                    "label_en": "Nuclear Experiment",
                    "label_fr": "Physique Nucléaire Expérimentale",
                    "children": [],
                },
                {
                    "id": "phys.nucl",
                    "label_en": "Nuclear Theory",
                    "label_fr": "Physique Nucléaire Théorique",
                    "children": [],
                },
                {
                    "id": "phys.phys",
                    "label_en": "Physics",
                    "label_fr": "Physique",
                    "children": [
                        {
                            "id": "phys.phys.phys-acc-ph",
                            "label_en": "Accelerator Physics",
                            "label_fr": "Physique des accélérateurs",
                            "children": [],
                        },
                        {
                            "id": "phys.phys.phys-ao-ph",
                            "label_en": "Atmospheric and Oceanic Physics",
                            "label_fr": "Physique Atmosphérique et Océanique",
                            "children": [],
                        },
                        {
                            "id": "phys.phys.phys-atm-ph",
                            "label_en": "Atomic and Molecular Clusters",
                            "label_fr": "Agrégats Moléculaires et Atomiques",
                            "children": [],
                        },
                        {
                            "id": "phys.phys.phys-atom-ph",
                            "label_en": "Atomic Physics",
                            "label_fr": "Physique Atomique",
                            "children": [],
                        },
                        {
                            "id": "phys.phys.phys-bio-ph",
                            "label_en": "Biological Physics",
                            "label_fr": "Biophysique",
                            "children": [],
                        },
                        {
                            "id": "phys.phys.phys-chem-ph",
                            "label_en": "Chemical Physics",
                            "label_fr": "Chimie-Physique",
                            "children": [],
                        },
                        {
                            "id": "phys.phys.phys-class-ph",
                            "label_en": "Classical Physics",
                            "label_fr": "Physique Classique",
                            "children": [],
                        },
                        {
                            "id": "phys.phys.phys-comp-ph",
                            "label_en": "Computational Physics",
                            "label_fr": "Physique Numérique",
                            "children": [],
                        },
                        {
                            "id": "phys.phys.phys-data-an",
                            "label_en": "Data Analysis, Statistics and Probability",
                            "label_fr": "Analyse de données, Statistiques et Probabilités",
                            "children": [],
                        },
                        {
                            "id": "phys.phys.phys-ed-ph",
                            "label_en": "Physics Education",
                            "label_fr": "Enseignement de la physique",
                            "children": [],
                        },
                        {
                            "id": "phys.phys.phys-flu-dyn",
                            "label_en": "Fluid Dynamics",
                            "label_fr": "Dynamique des Fluides",
                            "children": [],
                        },
                        {
                            "id": "phys.phys.phys-gen-ph",
                            "label_en": "General Physics",
                            "label_fr": "Physique Générale",
                            "children": [],
                        },
                        {
                            "id": "phys.phys.phys-geo-ph",
                            "label_en": "Geophysics",
                            "label_fr": "Géophysique",
                            "children": [],
                        },
                        {
                            "id": "phys.phys.phys-hist-ph",
                            "label_en": "History of Physics",
                            "label_fr": "Histoire de la Physique",
                            "children": [],
                        },
                        {
                            "id": "phys.phys.phys-ins-det",
                            "label_en": "Instrumentation and Detectors",
                            "label_fr": "Instrumentations et Détecteurs",
                            "children": [],
                        },
                        {
                            "id": "phys.phys.phys-med-ph",
                            "label_en": "Medical Physics",
                            "label_fr": "Physique Médicale",
                            "children": [],
                        },
                        {
                            "id": "phys.phys.phys-optics",
                            "label_en": "Optics",
                            "label_fr": "Optique",
                            "children": [],
                        },
                        {
                            "id": "phys.phys.phys-plasm-ph",
                            "label_en": "Plasma Physics",
                            "label_fr": "Physique des plasmas",
                            "children": [],
                        },
                        {
                            "id": "phys.phys.phys-pop-ph",
                            "label_en": "Popular Physics",
                            "label_fr": "Physique : vulgarisation",
                            "children": [],
                        },
                        {
                            "id": "phys.phys.phys-soc-ph",
                            "label_en": "Physics and Society",
                            "label_fr": "Physique et Société",
                            "children": [],
                        },
                        {
                            "id": "phys.phys.phys-space-ph",
                            "label_en": "Space Physics",
                            "label_fr": "Physique de l'espace",
                            "children": [],
                        },
                    ],
                },
                {
                    "id": "phys.qphy",
                    "label_en": "Quantum Physics",
                    "label_fr": "Physique Quantique",
                    "children": [],
                },
                {
                    "id": "phys.hist",
                    "label_en": "Physics archives",
                    "label_fr": "Articles anciens",
                    "children": [],
                },
            ],
        },
        {
            "id": "scco",
            "label_en": "Cognitive science",
            "label_fr": "Sciences cognitives",
            "children": [
                {
                    "id": "scco.comp",
                    "label_en": "Computer science",
                    "label_fr": "Informatique",
                    "children": [],
                },
                {
                    "id": "scco.ling",
                    "label_en": "Linguistics",
                    "label_fr": "Linguistique",
                    "children": [],
                },
                {
                    "id": "scco.neur",
                    "label_en": "Neuroscience",
                    "label_fr": "Neurosciences",
                    "children": [],
                },
                {
                    "id": "scco.psyc",
                    "label_en": "Psychology",
                    "label_fr": "Psychologie",
                    "children": [],
                },
            ],
        },
        {
            "id": "sde",
            "label_en": "Environmental Sciences",
            "label_fr": "Sciences de l'environnement",
            "children": [
                {
                    "id": "sde.be",
                    "label_en": "Biodiversity and Ecology",
                    "label_fr": "Biodiversité et Ecologie",
                    "children": [],
                },
                {
                    "id": "sde.es",
                    "label_en": "Environmental and Society",
                    "label_fr": "Environnement et Société",
                    "children": [],
                },
                {
                    "id": "sde.mcg",
                    "label_en": "Global Changes",
                    "label_fr": "Milieux et Changements globaux",
                    "children": [],
                },
                {
                    "id": "sde.ie",
                    "label_en": "Environmental Engineering",
                    "label_fr": "Ingénierie de l'environnement",
                    "children": [],
                },
            ],
        },
        {
            "id": "sdu",
            "label_en": "Sciences of the Universe",
            "label_fr": "Planète et Univers",
            "children": [
                {
                    "id": "sdu.astr",
                    "label_en": "Astrophysics",
                    "label_fr": "Astrophysique",
                    "children": [
                        {
                            "id": "sdu.astr.co",
                            "label_en": "Cosmology and Extra-Galactic Astrophysics",
                            "label_fr": "Cosmologie et astrophysique extra-galactique",
                            "children": [],
                        },
                        {
                            "id": "sdu.astr.ep",
                            "label_en": "Earth and Planetary Astrophysics",
                            "label_fr": "Planétologie et astrophysique de la terre",
                            "children": [],
                        },
                        {
                            "id": "sdu.astr.ga",
                            "label_en": "Galactic Astrophysics",
                            "label_fr": "Astrophysique galactique",
                            "children": [],
                        },
                        {
                            "id": "sdu.astr.he",
                            "label_en": "High Energy Astrophysical Phenomena",
                            "label_fr": "Phénomènes cosmiques de haute energie",
                            "children": [],
                        },
                        {
                            "id": "sdu.astr.im",
                            "label_en": "Instrumentation and Methods for Astrophysic",
                            "label_fr": "Instrumentation et méthodes pour l'astrophysique",
                            "children": [],
                        },
                        {
                            "id": "sdu.astr.sr",
                            "label_en": "Solar and Stellar Astrophysics",
                            "label_fr": "Astrophysique stellaire et solaire",
                            "children": [],
                        },
                    ],
                },
                {
                    "id": "sdu.envi",
                    "label_en": "Continental interfaces, environment",
                    "label_fr": "Interfaces continentales, environnement",
                    "children": [],
                },
                {
                    "id": "sdu.ocean",
                    "label_en": "Ocean, Atmosphere",
                    "label_fr": "Océan, Atmosphère",
                    "children": [],
                },
                {
                    "id": "sdu.other",
                    "label_en": "Other",
                    "label_fr": "Autre",
                    "children": [],
                },
                {
                    "id": "sdu.stu",
                    "label_en": "Earth Sciences",
                    "label_fr": "Sciences de la Terre",
                    "children": [
                        {
                            "id": "sdu.stu.ag",
                            "label_en": "Applied geology",
                            "label_fr": "Géologie appliquée",
                            "children": [],
                        },
                        {
                            "id": "sdu.stu.cl",
                            "label_en": "Climatology",
                            "label_fr": "Climatologie",
                            "children": [],
                        },
                        {
                            "id": "sdu.stu.gc",
                            "label_en": "Geochemistry",
                            "label_fr": "Géochimie",
                            "children": [],
                        },
                        {
                            "id": "sdu.stu.gl",
                            "label_en": "Glaciology",
                            "label_fr": "Glaciologie",
                            "children": [],
                        },
                        {
                            "id": "sdu.stu.gm",
                            "label_en": "Geomorphology",
                            "label_fr": "Géomorphologie",
                            "children": [],
                        },
                        {
                            "id": "sdu.stu.gp",
                            "label_en": "Geophysics",
                            "label_fr": "Géophysique",
                            "children": [],
                        },
                        {
                            "id": "sdu.stu.hy",
                            "label_en": "Hydrology",
                            "label_fr": "Hydrologie",
                            "children": [],
                        },
                        {
                            "id": "sdu.stu.me",
                            "label_en": "Meteorology",
                            "label_fr": "Météorologie",
                            "children": [],
                        },
                        {
                            "id": "sdu.stu.mi",
                            "label_en": "Mineralogy",
                            "label_fr": "Minéralogie",
                            "children": [],
                        },
                        {
                            "id": "sdu.stu.oc",
                            "label_en": "Oceanography",
                            "label_fr": "Océanographie",
                            "children": [],
                        },
                        {
                            "id": "sdu.stu.pe",
                            "label_en": "Petrography",
                            "label_fr": "Pétrographie",
                            "children": [],
                        },
                        {
                            "id": "sdu.stu.pg",
                            "label_en": "Paleontology",
                            "label_fr": "Paléontologie",
                            "children": [],
                        },
                        {
                            "id": "sdu.stu.pl",
                            "label_en": "Planetology",
                            "label_fr": "Planétologie",
                            "children": [],
                        },
                        {
                            "id": "sdu.stu.st",
                            "label_en": "Stratigraphy",
                            "label_fr": "Stratigraphie",
                            "children": [],
                        },
                        {
                            "id": "sdu.stu.te",
                            "label_en": "Tectonics",
                            "label_fr": "Tectonique",
                            "children": [],
                        },
                        {
                            "id": "sdu.stu.vo",
                            "label_en": "Volcanology",
                            "label_fr": "Volcanologie",
                            "children": [],
                        },
                    ],
                },
            ],
        },
        {
            "id": "sdv",
            "label_en": "Life Sciences",
            "label_fr": "Sciences du Vivant",
            "children": [
                {
                    "id": "sdv.aen",
                    "label_en": "Food and Nutrition",
                    "label_fr": "Alimentation et Nutrition",
                    "children": [],
                },
                {
                    "id": "sdv.ba",
                    "label_en": "Animal biology",
                    "label_fr": "Biologie animale",
                    "children": [
                        {
                            "id": "sdv.ba.mvsa",
                            "label_en": "Veterinary medicine and animal Health",
                            "label_fr": "Médecine vétérinaire et santé animal",
                            "children": [],
                        },
                        {
                            "id": "sdv.ba.zi",
                            "label_en": "Invertebrate Zoology",
                            "label_fr": "Zoologie des invertébrés",
                            "children": [],
                        },
                        {
                            "id": "sdv.ba.zv",
                            "label_en": "Vertebrate Zoology",
                            "label_fr": "Zoologie des vertébrés",
                            "children": [],
                        },
                    ],
                },
                {
                    "id": "sdv.bbm",
                    "label_en": "Biochemistry, Molecular Biology",
                    "label_fr": "Biochimie, Biologie Moléculaire",
                    "children": [
                        {
                            "id": "sdv.bbm.bc",
                            "label_en": "Biomolecules",
                            "label_fr": "Biochimie",
                            "children": [],
                        },
                        {
                            "id": "sdv.bbm.bm",
                            "label_en": "Molecular biology",
                            "label_fr": "Biologie moléculaire",
                            "children": [],
                        },
                        {
                            "id": "sdv.bbm.bp",
                            "label_en": "Biophysics",
                            "label_fr": "Biophysique",
                            "children": [],
                        },
                        {
                            "id": "sdv.bbm.bs",
                            "label_en": "Biomolecules",
                            "label_fr": "Biologie structurale",
                            "children": [],
                        },
                        {
                            "id": "sdv.bbm.gtp",
                            "label_en": "Genomics",
                            "label_fr": "Génomique, Transcriptomique et Protéomique",
                            "children": [],
                        },
                        {
                            "id": "sdv.bbm.mn",
                            "label_en": "Molecular Networks",
                            "label_fr": "Réseaux moléculaires",
                            "children": [],
                        },
                    ],
                },
                {
                    "id": "sdv.bc",
                    "label_en": "Cellular Biology",
                    "label_fr": "Biologie cellulaire",
                    "children": [
                        {
                            "id": "sdv.bc.bc",
                            "label_en": "Subcellular Processes",
                            "label_fr": "Organisation et fonctions cellulaires",
                            "children": [],
                        },
                        {
                            "id": "sdv.bc.ic",
                            "label_en": "Cell Behavior",
                            "label_fr": "Interactions cellulaires",
                            "children": [],
                        },
                    ],
                },
                {
                    "id": "sdv.bdd",
                    "label_en": "Development Biology",
                    "label_fr": "Biologie du développement",
                    "children": [
                        {
                            "id": "sdv.bdd.eo",
                            "label_en": "Embryology and Organogenesis",
                            "label_fr": "Embryologie et organogenèse",
                            "children": [],
                        },
                        {
                            "id": "sdv.bdd.gam",
                            "label_en": "Gametogenesis",
                            "label_fr": "Gamétogenèse",
                            "children": [],
                        },
                        {
                            "id": "sdv.bdd.mor",
                            "label_en": "Morphogenesis",
                            "label_fr": "Morphogenèse",
                            "children": [],
                        },
                    ],
                },
                {
                    "id": "sdv.bdlr",
                    "label_en": "Reproductive Biology",
                    "label_fr": "Biologie de la reproduction",
                    "children": [
                        {
                            "id": "sdv.bdlr.ra",
                            "label_en": "Asexual reproduction",
                            "label_fr": "Reproduction asexuée",
                            "children": [],
                        },
                        {
                            "id": "sdv.bdlr.rs",
                            "label_en": "Sexual reproduction",
                            "label_fr": "Reproduction sexuée",
                            "children": [],
                        },
                    ],
                },
                {
                    "id": "sdv.bibs",
                    "label_en": "Quantitative Methods",
                    "label_fr": "Bio-Informatique, Biologie Systémique",
                    "children": [],
                },
                {
                    "id": "sdv.bid",
                    "label_en": "Biodiversity",
                    "label_fr": "Biodiversité",
                    "children": [
                        {
                            "id": "sdv.bid.evo",
                            "label_en": "Populations and Evolution",
                            "label_fr": "Evolution",
                            "children": [],
                        },
                        {
                            "id": "sdv.bid.spt",
                            "label_en": "Systematics, Phylogenetics and taxonomy",
                            "label_fr": "Systématique, phylogénie et taxonomie",
                            "children": [],
                        },
                    ],
                },
                {
                    "id": "sdv.bio",
                    "label_en": "Biotechnology",
                    "label_fr": "Biotechnologies",
                    "children": [],
                },
                {
                    "id": "sdv.bv",
                    "label_en": "Vegetal Biology",
                    "label_fr": "Biologie végétale",
                    "children": [
                        {
                            "id": "sdv.bv.ap",
                            "label_en": "Plant breeding",
                            "label_fr": "Amélioration des plantes",
                            "children": [],
                        },
                        {
                            "id": "sdv.bv.bot",
                            "label_en": "Botanics",
                            "label_fr": "Botanique",
                            "children": [],
                        },
                        {
                            "id": "sdv.bv.pep",
                            "label_en": "Phytopathology and phytopharmacy",
                            "label_fr": "Phytopathologie et phytopharmacie",
                            "children": [],
                        },
                    ],
                },
                {
                    "id": "sdv.can",
                    "label_en": "Cancer",
                    "label_fr": "Cancer",
                    "children": [],
                },
                {
                    "id": "sdv.ee",
                    "label_en": "Ecology, environment",
                    "label_fr": "Ecologie, Environnement",
                    "children": [
                        {
                            "id": "sdv.ee.bio",
                            "label_en": "Bioclimatology",
                            "label_fr": "Bioclimatologie",
                            "children": [],
                        },
                        {
                            "id": "sdv.ee.eco",
                            "label_en": "Ecosystems",
                            "label_fr": "Ecosystèmes",
                            "children": [],
                        },
                        {
                            "id": "sdv.ee.ieo",
                            "label_en": "Symbiosis",
                            "label_fr": "Interactions entre organismes",
                            "children": [],
                        },
                        {
                            "id": "sdv.ee.sant",
                            "label_en": "Health",
                            "label_fr": "Santé",
                            "children": [],
                        },
                    ],
                },
                {
                    "id": "sdv.eth",
                    "label_en": "Ethics",
                    "label_fr": "Ethique",
                    "children": [],
                },
                {
                    "id": "sdv.gen",
                    "label_en": "Genetics",
                    "label_fr": "Génétique",
                    "children": [
                        {
                            "id": "sdv.gen.ga",
                            "label_en": "Animal genetics",
                            "label_fr": "Génétique animale",
                            "children": [],
                        },
                        {
                            "id": "sdv.gen.gh",
                            "label_en": "Human genetics",
                            "label_fr": "Génétique humaine",
                            "children": [],
                        },
                        {
                            "id": "sdv.gen.gpl",
                            "label_en": "Plants genetics",
                            "label_fr": "Génétique des plantes",
                            "children": [],
                        },
                        {
                            "id": "sdv.gen.gpo",
                            "label_en": "Populations and Evolution",
                            "label_fr": "Génétique des populations",
                            "children": [],
                        },
                    ],
                },
                {
                    "id": "sdv.ib",
                    "label_en": "Bioengineering",
                    "label_fr": "Ingénierie biomédicale",
                    "children": [
                        {
                            "id": "sdv.ib.bio",
                            "label_en": "Biomaterials",
                            "label_fr": "Biomatériaux",
                            "children": [],
                        },
                        {
                            "id": "sdv.ib.ima",
                            "label_en": "Imaging",
                            "label_fr": "Imagerie",
                            "children": [],
                        },
                        {
                            "id": "sdv.ib.mn",
                            "label_en": "Nuclear medicine",
                            "label_fr": "Médecine nucléaire",
                            "children": [],
                        },
                    ],
                },
                {
                    "id": "sdv.ida",
                    "label_en": "Food engineering",
                    "label_fr": "Ingénierie des aliments",
                    "children": [],
                },
                {
                    "id": "sdv.imm",
                    "label_en": "Immunology",
                    "label_fr": "Immunologie",
                    "children": [
                        {
                            "id": "sdv.imm.all",
                            "label_en": "Allergology",
                            "label_fr": "Allergologie",
                            "children": [],
                        },
                        {
                            "id": "sdv.imm.ia",
                            "label_en": "Adaptive immunology",
                            "label_fr": "Immunité adaptative",
                            "children": [],
                        },
                        {
                            "id": "sdv.imm.ii",
                            "label_en": "Innate immunity",
                            "label_fr": "Immunité innée",
                            "children": [],
                        },
                        {
                            "id": "sdv.imm.imm",
                            "label_en": "Immunotherapy",
                            "label_fr": "Immunothérapie",
                            "children": [],
                        },
                        {
                            "id": "sdv.imm.vac",
                            "label_en": "Vaccinology",
                            "label_fr": "Vaccinologie",
                            "children": [],
                        },
                    ],
                },
                {
                    "id": "sdv.mhep",
                    "label_en": "Human health and pathology",
                    "label_fr": "Médecine humaine et pathologie",
                    "children": [
                        {
                            "id": "sdv.mhep.aha",
                            "label_en": "Tissues and Organs",
                            "label_fr": "Anatomie, Histologie, Anatomopathologie",
                            "children": [],
                        },
                        {
                            "id": "sdv.mhep.chi",
                            "label_en": "Surgery",
                            "label_fr": "Chirurgie",
                            "children": [],
                        },
                        {
                            "id": "sdv.mhep.csc",
                            "label_en": "Cardiology and cardiovascular system",
                            "label_fr": "Cardiologie et système cardiovasculaire",
                            "children": [],
                        },
                        {
                            "id": "sdv.mhep.derm",
                            "label_en": "Dermatology",
                            "label_fr": "Dermatologie",
                            "children": [],
                        },
                        {
                            "id": "sdv.mhep.em",
                            "label_en": "Endocrinology and metabolism",
                            "label_fr": "Endocrinologie et métabolisme",
                            "children": [],
                        },
                        {
                            "id": "sdv.mhep.geg",
                            "label_en": "Geriatry and gerontology",
                            "label_fr": "Gériatrie et gérontologie",
                            "children": [],
                        },
                        {
                            "id": "sdv.mhep.geo",
                            "label_en": "Gynecology and obstetrics",
                            "label_fr": "Gynécologie et obstétrique",
                            "children": [],
                        },
                        {
                            "id": "sdv.mhep.heg",
                            "label_en": "Hépatology and Gastroenterology",
                            "label_fr": "Hépatologie et Gastroentérologie",
                            "children": [],
                        },
                        {
                            "id": "sdv.mhep.hem",
                            "label_en": "Hematology",
                            "label_fr": "Hématologie",
                            "children": [],
                        },
                        {
                            "id": "sdv.mhep.me",
                            "label_en": "Emerging diseases",
                            "label_fr": "Maladies émergentes",
                            "children": [],
                        },
                        {
                            "id": "sdv.mhep.mi",
                            "label_en": "Infectious diseases",
                            "label_fr": "Maladies infectieuses",
                            "children": [],
                        },
                        {
                            "id": "sdv.mhep.os",
                            "label_en": "Sensory Organs",
                            "label_fr": "Organes des sens",
                            "children": [],
                        },
                        {
                            "id": "sdv.mhep.ped",
                            "label_en": "Pediatrics",
                            "label_fr": "Pédiatrie",
                            "children": [],
                        },
                        {
                            "id": "sdv.mhep.phy",
                            "label_en": "Tissues and Organs",
                            "label_fr": "Physiologie",
                            "children": [],
                        },
                        {
                            "id": "sdv.mhep.psm",
                            "label_en": "Psychiatrics and mental health",
                            "label_fr": "Psychiatrie et santé mentale",
                            "children": [],
                        },
                        {
                            "id": "sdv.mhep.psr",
                            "label_en": "Pulmonology and respiratory tract",
                            "label_fr": "Pneumologie et système respiratoire",
                            "children": [],
                        },
                        {
                            "id": "sdv.mhep.rsoa",
                            "label_en": "Rhumatology and musculoskeletal system",
                            "label_fr": "Rhumatologie et système ostéo-articulaire",
                            "children": [],
                        },
                        {
                            "id": "sdv.mhep.un",
                            "label_en": "Urology and Nephrology",
                            "label_fr": "Urologie et Néphrologie",
                            "children": [],
                        },
                    ],
                },
                {
                    "id": "sdv.mp",
                    "label_en": "Microbiology and Parasitology",
                    "label_fr": "Microbiologie et Parasitologie",
                    "children": [
                        {
                            "id": "sdv.mp.bac",
                            "label_en": "Bacteriology",
                            "label_fr": "Bactériologie",
                            "children": [],
                        },
                        {
                            "id": "sdv.mp.myc",
                            "label_en": "Mycology",
                            "label_fr": "Mycologie",
                            "children": [],
                        },
                        {
                            "id": "sdv.mp.par",
                            "label_en": "Parasitology",
                            "label_fr": "Parasitologie",
                            "children": [],
                        },
                        {
                            "id": "sdv.mp.pro",
                            "label_en": "Protistology",
                            "label_fr": "Protistologie",
                            "children": [],
                        },
                        {
                            "id": "sdv.mp.vir",
                            "label_en": "Virology",
                            "label_fr": "Virologie",
                            "children": [],
                        },
                    ],
                },
                {
                    "id": "sdv.neu",
                    "label_en": "Neurons and Cognition",
                    "label_fr": "Neurosciences",
                    "children": [
                        {
                            "id": "sdv.neu.nb",
                            "label_en": "Neurobiology",
                            "label_fr": "Neurobiologie",
                            "children": [],
                        },
                        {
                            "id": "sdv.neu.pc",
                            "label_en": "Psychology and behavior",
                            "label_fr": "Psychologie et comportements",
                            "children": [],
                        },
                        {
                            "id": "sdv.neu.sc",
                            "label_en": "Cognitive Sciences",
                            "label_fr": "Sciences cognitives",
                            "children": [],
                        },
                    ],
                },
                {
                    "id": "sdv.ot",
                    "label_en": "Other",
                    "label_fr": "Autre",
                    "children": [],
                },
                {
                    "id": "sdv.sa",
                    "label_en": "Agricultural sciences",
                    "label_fr": "Sciences agricoles",
                    "children": [
                        {
                            "id": "sdv.sa.aep",
                            "label_en": "Agriculture, economy and politics",
                            "label_fr": "Agriculture, économie et politique",
                            "children": [],
                        },
                        {
                            "id": "sdv.sa.agro",
                            "label_en": "Agronomy",
                            "label_fr": "Agronomie",
                            "children": [],
                        },
                        {
                            "id": "sdv.sa.hort",
                            "label_en": "Horticulture",
                            "label_fr": "Horticulture",
                            "children": [],
                        },
                        {
                            "id": "sdv.sa.sds",
                            "label_en": "Soil study",
                            "label_fr": "Science des sols",
                            "children": [],
                        },
                        {
                            "id": "sdv.sa.sf",
                            "label_en": "Silviculture, forestry",
                            "label_fr": "Sylviculture, foresterie",
                            "children": [],
                        },
                        {
                            "id": "sdv.sa.spa",
                            "label_en": "Animal production studies",
                            "label_fr": "Science des productions animales",
                            "children": [],
                        },
                        {
                            "id": "sdv.sa.sta",
                            "label_en": "Sciences and technics of agriculture",
                            "label_fr": "Sciences et techniques de l'agriculture",
                            "children": [],
                        },
                        {
                            "id": "sdv.sa.stp",
                            "label_en": "Sciences and technics of fishery",
                            "label_fr": "Sciences et techniques des pêches",
                            "children": [],
                        },
                        {
                            "id": "sdv.sa.zoo",
                            "label_en": "Zootechny",
                            "label_fr": "Zootechnie",
                            "children": [],
                        },
                    ],
                },
                {
                    "id": "sdv.sp",
                    "label_en": "Pharmaceutical sciences",
                    "label_fr": "Sciences pharmaceutiques",
                    "children": [
                        {
                            "id": "sdv.sp.med",
                            "label_en": "Medication",
                            "label_fr": "Médicaments",
                            "children": [],
                        },
                        {
                            "id": "sdv.sp.pg",
                            "label_en": "Galenic pharmacology",
                            "label_fr": "Pharmacie galénique",
                            "children": [],
                        },
                        {
                            "id": "sdv.sp.pharma",
                            "label_en": "Pharmacology",
                            "label_fr": "Pharmacologie",
                            "children": [],
                        },
                    ],
                },
                {
                    "id": "sdv.spee",
                    "label_en": "Santé publique et épidémiologie",
                    "label_fr": "Santé publique et épidémiologie",
                    "children": [],
                },
                {
                    "id": "sdv.tox",
                    "label_en": "Toxicology",
                    "label_fr": "Toxicologie",
                    "children": [
                        {
                            "id": "sdv.tox.eco",
                            "label_en": "Ecotoxicology",
                            "label_fr": "Ecotoxicologie",
                            "children": [],
                        },
                        {
                            "id": "sdv.tox.tca",
                            "label_en": "Toxicology and food chain",
                            "label_fr": "Toxicologie et chaîne alimentaire",
                            "children": [],
                        },
                        {
                            "id": "sdv.tox.tvm",
                            "label_en": "Vegetal toxicology and mycotoxicology",
                            "label_fr": "Toxicologie végétale et mycotoxicologie",
                            "children": [],
                        },
                    ],
                },
            ],
        },
        {
            "id": "shs",
            "label_en": "Humanities and Social Sciences",
            "label_fr": "Sciences de l'Homme et Société",
            "children": [
                {
                    "id": "shs.anthro-bio",
                    "label_en": "Biological anthropology",
                    "label_fr": "Anthropologie biologique",
                    "children": [],
                },
                {
                    "id": "shs.anthro-se",
                    "label_en": "Social Anthropology and ethnology",
                    "label_fr": "Anthropologie sociale et ethnologie",
                    "children": [],
                },
                {
                    "id": "shs.archeo",
                    "label_en": "Archaeology and Prehistory",
                    "label_fr": "Archéologie et Préhistoire",
                    "children": [],
                },
                {
                    "id": "shs.archi",
                    "label_en": "Architecture, space management",
                    "label_fr": "Architecture, aménagement de l'espace",
                    "children": [],
                },
                {
                    "id": "shs.art",
                    "label_en": "Art and art history",
                    "label_fr": "Art et histoire de l'art",
                    "children": [],
                },
                {
                    "id": "shs.class",
                    "label_en": "Classical studies",
                    "label_fr": "Etudes classiques",
                    "children": [],
                },
                {
                    "id": "shs.demo",
                    "label_en": "Demography",
                    "label_fr": "Démographie",
                    "children": [],
                },
                {
                    "id": "shs.droit",
                    "label_en": "Law",
                    "label_fr": "Droit",
                    "children": [],
                },
                {
                    "id": "shs.eco",
                    "label_en": "Economics and Finance",
                    "label_fr": "Economies et finances",
                    "children": [],
                },
                {
                    "id": "shs.edu",
                    "label_en": "Education",
                    "label_fr": "Education",
                    "children": [],
                },
                {
                    "id": "shs.envir",
                    "label_en": "Environmental studies",
                    "label_fr": "Etudes de l'environnement",
                    "children": [],
                },
                {
                    "id": "shs.genre",
                    "label_en": "Gender studies",
                    "label_fr": "Etudes sur le genre",
                    "children": [],
                },
                {
                    "id": "shs.geo",
                    "label_en": "Geography",
                    "label_fr": "Géographie",
                    "children": [],
                },
                {
                    "id": "shs.gestion",
                    "label_en": "Business administration",
                    "label_fr": "Gestion et management",
                    "children": [],
                },
                {
                    "id": "shs.hisphilso",
                    "label_en": "History, Philosophy and Sociology of Sciences",
                    "label_fr": "Histoire, Philosophie et Sociologie des sciences",
                    "children": [],
                },
                {
                    "id": "shs.hist",
                    "label_en": "History",
                    "label_fr": "Histoire",
                    "children": [],
                },
                {
                    "id": "shs.info",
                    "label_en": "Library and information sciences",
                    "label_fr": "Sciences de l'information et de la communication",
                    "children": [],
                },
                {
                    "id": "shs.langue",
                    "label_en": "Linguistics",
                    "label_fr": "Linguistique",
                    "children": [],
                },
                {
                    "id": "shs.litt",
                    "label_en": "Literature",
                    "label_fr": "Littératures",
                    "children": [],
                },
                {
                    "id": "shs.museo",
                    "label_en": "Cultural heritage and museology",
                    "label_fr": "Héritage culturel et muséologie",
                    "children": [],
                },
                {
                    "id": "shs.musiq",
                    "label_en": "Musicology and performing arts",
                    "label_fr": "Musique, musicologie et arts de la scène",
                    "children": [],
                },
                {
                    "id": "shs.phil",
                    "label_en": "Philosophy",
                    "label_fr": "Philosophie",
                    "children": [],
                },
                {
                    "id": "shs.psy",
                    "label_en": "Psychology",
                    "label_fr": "Psychologie",
                    "children": [],
                },
                {
                    "id": "shs.relig",
                    "label_en": "Religions",
                    "label_fr": "Religions",
                    "children": [],
                },
                {
                    "id": "shs.scipo",
                    "label_en": "Political science",
                    "label_fr": "Science politique",
                    "children": [],
                },
                {
                    "id": "shs.socio",
                    "label_en": "Sociology",
                    "label_fr": "Sociologie",
                    "children": [],
                },
                {
                    "id": "shs.stat",
                    "label_en": "Methods and statistics",
                    "label_fr": "Méthodes et statistiques",
                    "children": [],
                },
            ],
        },
        {
            "id": "spi",
            "label_en": "Engineering Sciences",
            "label_fr": "Sciences de l'ingénieur",
            "children": [
                {
                    "id": "spi.acou",
                    "label_en": "Acoustics",
                    "label_fr": "Acoustique",
                    "children": [],
                },
                {
                    "id": "spi.auto",
                    "label_en": "Automatic",
                    "label_fr": "Automatique / Robotique",
                    "children": [],
                },
                {
                    "id": "spi.elec",
                    "label_en": "Electromagnetism",
                    "label_fr": "Electromagnétisme",
                    "children": [],
                },
                {
                    "id": "spi.fluid",
                    "label_en": "Reactive fluid environment",
                    "label_fr": "Milieux fluides et réactifs",
                    "children": [],
                },
                {
                    "id": "spi.gproc",
                    "label_en": "Chemical and Process Engineering",
                    "label_fr": "Génie des procédés",
                    "children": [],
                },
                {
                    "id": "spi.mat",
                    "label_en": "Materials",
                    "label_fr": "Matériaux",
                    "children": [],
                },
                {
                    "id": "spi.meca",
                    "label_en": "Mechanics",
                    "label_fr": "Mécanique",
                    "children": [
                        {
                            "id": "spi.meca.biom",
                            "label_en": "Biomechanics",
                            "label_fr": "Biomécanique",
                            "children": [],
                        },
                        {
                            "id": "spi.meca.geme",
                            "label_en": "Mechanical engineering",
                            "label_fr": "Génie mécanique",
                            "children": [],
                        },
                        {
                            "id": "spi.meca.mefl",
                            "label_en": "Fluids mechanics",
                            "label_fr": "Mécanique des fluides",
                            "children": [],
                        },
                        {
                            "id": "spi.meca.mema",
                            "label_en": "Mechanics of materials",
                            "label_fr": "Mécanique des matériaux",
                            "children": [],
                        },
                        {
                            "id": "spi.meca.msmeca",
                            "label_en": "Materials and structures in mechanics",
                            "label_fr": "Matériaux et structures en mécanique",
                            "children": [],
                        },
                        {
                            "id": "spi.meca.solid",
                            "label_en": "Mechanics of the solides",
                            "label_fr": "Mécanique des solides",
                            "children": [],
                        },
                        {
                            "id": "spi.meca.stru",
                            "label_en": "Mechanics of the structures",
                            "label_fr": "Mécanique des structures",
                            "children": [],
                        },
                        {
                            "id": "spi.meca.ther",
                            "label_en": "Thermics",
                            "label_fr": "Thermique",
                            "children": [],
                        },
                        {
                            "id": "spi.meca.vibr",
                            "label_en": "Vibrations",
                            "label_fr": "Vibrations",
                            "children": [],
                        },
                    ],
                },
                {
                    "id": "spi.nano",
                    "label_en": "Micro and nanotechnologies/Microelectronics",
                    "label_fr": "Micro et nanotechnologies/Microélectronique",
                    "children": [],
                },
                {
                    "id": "spi.nrj",
                    "label_en": "Electric power",
                    "label_fr": "Energie électrique",
                    "children": [],
                },
                {
                    "id": "spi.opti",
                    "label_en": "Optics / Photonic",
                    "label_fr": "Optique / photonique",
                    "children": [],
                },
                {
                    "id": "spi.other",
                    "label_en": "Other",
                    "label_fr": "Autre",
                    "children": [],
                },
                {
                    "id": "spi.plasma",
                    "label_en": "Plasmas",
                    "label_fr": "Plasmas",
                    "children": [],
                },
                {
                    "id": "spi.signal",
                    "label_en": "Signal and Image processing",
                    "label_fr": "Traitement du signal et de l'image",
                    "children": [],
                },
                {
                    "id": "spi.tron",
                    "label_en": "Electronics",
                    "label_fr": "Electronique",
                    "children": [],
                },
                {
                    "id": "spi.gciv",
                    "label_en": "Civil Engineering",
                    "label_fr": "Génie civil",
                    "children": [
                        {
                            "id": "spi.gciv.ch",
                            "label_en": "Construction hydraulique",
                            "label_fr": "Construction hydraulique",
                            "children": [],
                        },
                        {
                            "id": "spi.gciv.cd",
                            "label_en": "Construction durable",
                            "label_fr": "Construction durable",
                            "children": [],
                        },
                        {
                            "id": "spi.gciv.dv",
                            "label_en": "Dynamique, vibrations",
                            "label_fr": "Dynamique, vibrations",
                            "children": [],
                        },
                        {
                            "id": "spi.gciv.ec",
                            "label_en": "Eco-conception",
                            "label_fr": "Eco-conception",
                            "children": [],
                        },
                        {
                            "id": "spi.gciv.gcn",
                            "label_en": "Génie civil nucléaire",
                            "label_fr": "Génie civil nucléaire",
                            "children": [],
                        },
                        {
                            "id": "spi.gciv.geotech",
                            "label_en": "Géotechnique",
                            "label_fr": "Géotechnique",
                            "children": [],
                        },
                        {
                            "id": "spi.gciv.it",
                            "label_en": "Infrastructures de transport",
                            "label_fr": "Infrastructures de transport",
                            "children": [],
                        },
                        {
                            "id": "spi.gciv.mat",
                            "label_en": "Matériaux composites et construction",
                            "label_fr": "Matériaux composites et construction",
                            "children": [],
                        },
                        {
                            "id": "spi.gciv.rhea",
                            "label_en": "Rehabilitation",
                            "label_fr": "Réhabilitation",
                            "children": [],
                        },
                        {
                            "id": "spi.gciv.risq",
                            "label_en": "Risques",
                            "label_fr": "Risques",
                            "children": [],
                        },
                        {
                            "id": "spi.gciv.struct",
                            "label_en": "Structures",
                            "label_fr": "Structures",
                            "children": [],
                        },
                    ],
                },
            ],
        },
        {
            "id": "stat",
            "label_en": "Statistics",
            "label_fr": "Statistiques",
            "children": [
                {
                    "id": "stat.ot",
                    "label_en": "Other Statistics",
                    "label_fr": "Autres",
                    "children": [],
                },
                {
                    "id": "stat.ap",
                    "label_en": "Applications",
                    "label_fr": "Applications",
                    "children": [],
                },
                {
                    "id": "stat.co",
                    "label_en": "Computation",
                    "label_fr": "Calcul",
                    "children": [],
                },
                {
                    "id": "stat.me",
                    "label_en": "Methodology",
                    "label_fr": "Méthodologie",
                    "children": [],
                },
                {
                    "id": "stat.th",
                    "label_en": "Statistics Theory",
                    "label_fr": "Théorie",
                    "children": [],
                },
                {
                    "id": "stat.ml",
                    "label_en": "Machine Learning",
                    "label_fr": "Machine Learning",
                    "children": [],
                },
            ],
        },
        {
            "id": "qfin",
            "label_en": "Quantitative Finance",
            "label_fr": "Économie et finance quantitative",
            "children": [
                {
                    "id": "qfin.cp",
                    "label_en": "Computational Finance",
                    "label_fr": "Finance quantitative",
                    "children": [],
                },
                {
                    "id": "qfin.gn",
                    "label_en": "General Finance",
                    "label_fr": "Finance",
                    "children": [],
                },
                {
                    "id": "qfin.pm",
                    "label_en": "Portfolio Management",
                    "label_fr": "Gestion de portefeuilles",
                    "children": [],
                },
                {
                    "id": "qfin.pr",
                    "label_en": "Pricing of Securities",
                    "label_fr": "Pricing",
                    "children": [],
                },
                {
                    "id": "qfin.rm",
                    "label_en": "Risk Management",
                    "label_fr": "Gestion des risques",
                    "children": [],
                },
                {
                    "id": "qfin.st",
                    "label_en": "Statistical Finance",
                    "label_fr": "Econométrie de la finance",
                    "children": [],
                },
                {
                    "id": "qfin.tr",
                    "label_en": "Trading and Market Microstructure",
                    "label_fr": "Microstructure des marchés",
                    "children": [],
                },
            ],
        },
    ]


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
