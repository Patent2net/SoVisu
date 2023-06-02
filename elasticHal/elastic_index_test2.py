import csv
import datetime
import json
import re

import dateutil.parser
from dateutil.relativedelta import relativedelta
from elasticsearch import helpers

from elasticHal.libs import (
    doi_enrichissement,
    elastic_formatting2,
    hal,
    keyword_enrichissement,
    location_docs,
    utils, test_static,
)
from elasticHal.libs.archivesOuvertes import get_aurehalId, get_concepts_and_keywords
from sovisuhal.libs import esActions
from sovisuhal.viewsActions import idhal_checkout
from ldap3 import ALL, Connection, Server
from decouple import config

es = esActions.es_connector()

mode = config("mode")  # Prod --> mode = 'Prod' en env Var

# defr d'un mapping pour chaque categorie de doc
# ATTENTTION partiel et redondant


def create_test_context():
    # Variables à automatiser plus tard
    idhal = "david-reymond"
    orcid = ""
    labo_accro = "IMSIC"
    idref = "test"
    labhalid = "527028"
    ldapid = "dreymond"
    structid = "198307662"
    """end of temp values"""
    # remplissage index test_laboratoire
    labo_message = get_labo_from_csv()
    print(labo_message)

    # remplissage index institution
    institution_message = get_institution_from_csv()
    print(institution_message)

    # remplissage index concepts
    concepts_message = indexe_expertises()
    print(concepts_message)

    # remplissage index test_chercheur
    idhal_test = idhal_checkout(idhal)
    if idhal_test > 0:
        indexe_chercheur(structid, ldapid, labo_accro, labhalid, idhal, idref, orcid)

    # remplissage des publications
    # scope_param = scope_p("idhal", researcher_id) # ne renvoit rien, idhal est le bon champ
    # On retrouve le chercheur
    scope_param = esActions.scope_term_multi([("idhal", idhal), ('category', "searcher")])
    chercheur = es.search(index="test2", query=scope_param)
    chercheur = chercheur["hits"]["hits"][0]["_source"]

    ## à ce stade, chercheur contient des trucs inutiles : concepts et profil (ce dernier est là pour test modèle en arborescence (parent-child)
    print(chercheur)
    # collecte et indexation des docs
    publications_message = collecte_docs(chercheur)
    print(publications_message)


def indexe_chercheur(structid, ldapid, labo_accro, labhalid, idhal, idref, orcid):  # self,
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
        # integration contenus
        create_searcher_concept_notices(idhal, aurehal)

    searcher_notice = {
        "name": nom,
        "type": chercheur_type,
        "function": emploi,
        "mail": mail[0],
        "orcId": orcid,
        "lab": labo_accro,
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
        "axis": labo_accro,  # TODO: INTERET DE CETTE KEY?
        "category": "searcher"
    }

    res = es.index(
        index="test2",
        document=searcher_notice,
        refresh="wait_for",
    )
    print("statut de la création d'index: ", res["result"])
    return ""


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
        count = es.count(index="domaines-hal-referentiel", query=scope_all())["count"]
        # resDomainesRef = es.search(index="domaines-hal-referentiel", query=scope_param, size=count)
        toutRef = [truc['_source']['chemin'] for truc in
                   es.search(index="domaines-hal-referentiel", query={'match_all': {}}, size=count)[
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

        resDomainesRef = es.search(index="domaines-hal-referentiel", query=req)
        for fiche in resDomainesRef['hits']['hits']:
            newFiche = fiche['_source']
            newFiche['validated'] = False  # domaines pas validés par défaut
            # Id proposition : valider les domaines par défaut et laisser la possibilité d'en valider d'autres par explorateur d'arbre ?
            newFiche['idhal'] = idhal  # taggage, l'idhal sert de clé
            # Et rajouts besoins spécifiques (genre précisions / notes...)

            # Puis on indexe la fiche
            es.index(index="test2", document=json.dumps(newFiche), refresh="wait_for",)


def get_labo_from_csv():
    # TODO:fonctionne pas si on lance 2 fois.. pas cherché aussi cf.
    laboratories_list = []
    scope_param = scope_all()
    count = es.count(index="test2", query=scope_param)["count"]
    print(count)
    res = es.search(index="test2", query=scope_param, size=count)
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
                laboratories_list.append(
                    elastic_formatting2.laboratory_format(laboratory)
                )
            else:
                # Compare les données des labos existant dans les deux listes
                pass  # çe qui suit plante au 2e lancement
                # for listed_lab in laboratories_list:
                #     if listed_lab["halStructId"] == laboratory["halStructId"]:
                #         if laboratory["structSirene"] not in listed_lab["structSirene"]:
                #             listed_lab["structSirene"].append(laboratory["structSirene"])

    helpers.bulk(es, laboratories_list, index="test2", refresh="wait_for")
    return "laboratories added"


def get_institution_from_csv(add_csv=True):
    institutions_list = []
    if add_csv:
        with open("data/structures.csv", encoding="utf-8") as csv_file:
            institution_csv = list(csv.DictReader(csv_file, delimiter=";"))

    for institution in institution_csv:
        # insert operations to make before append in the list for indexation
        institutions_list.append(elastic_formatting2.institution_format(institution))

    helpers.bulk(es, institutions_list, index="test2", refresh="wait_for")

    return "institutions added"


def creeFiche(dom, par):
    fiche = dict()
    fiche['chemin'] = "domAurehal." + dom[
        'id']  # .replace('.',',')  # donnera le chemin d'accès de l'arborescence. i.e: chercher .shs

    # https://www.mongodb.com/docs/manual/tutorial/model-tree-structures-with-materialized-paths/

    fiche['label_en'] = dom['label_en']
    fiche['label_fr'] = dom['label_fr']
    fiche["category"] = "expertise"
    fiche["referentiel"] = "hal"
    return fiche


def GenereReferentiel(arbre, par):
    fiches = []
    if isinstance(arbre, list):
        for dom in arbre:
            fiche = dict()
            if "children" in dom.keys():
                # {'id': 'chim.anal', 'label_en': 'Analytical chemistry', 'label_fr': 'Chimie analytique', 'children': []}
                if len(dom['children']) != 0:
                    fiches.append(creeFiche(dom, par))
                    for sousdom in dom['children']:
                        temp = GenereReferentiel(sousdom, par=dom['id'])
                        if isinstance(temp, dict):
                            fiches.append(temp)
                        elif isinstance(temp, list):
                            for truc in temp:
                                fiches.append(truc)
                        else:
                            pass

                else:
                    fiches.append(creeFiche(dom, par))
            else:

                fiches.append(creeFiche(dom, par))
        fiches.append(creeFiche(dom, par))
    else:
        fiches.append(creeFiche(arbre, par))
        if "children" in arbre.keys():
            # {'id': 'chim.anal', 'label_en': 'Analytical chemistry', 'label_fr': 'Chimie analytique', 'children': []}
            if len(arbre['children']) != 0:
                fiches.append(creeFiche(arbre, par))
                for sousdom in arbre['children']:
                    temp = GenereReferentiel(sousdom, par=arbre['id'])
                    if isinstance(temp, dict):
                        fiches.append(temp)
                    elif isinstance(temp, list):
                        for truc in temp:
                            fiches.append(truc)
                    else:
                        pass

            else:
                pass
        else:
            pass

    return fiches


def indexe_expertises():
    """Les compétences issues d'Aurehal sont indexées en tant que document dans l'index domaines-hal-referentiel.
      Les chercheurs valident ou pas celle issues de HAL, en rajoutent éventuellement. Cette action, copie la fiche
      et l'estampille à son idhal.
    """
    concept_list = GenereReferentiel(test_static.concepts(), "")

    res = helpers.bulk(es, concept_list, index="domaines-hal-referentiel", refresh="wait_for")
    return str(res[0]), " Concepts added, in index domaines-hal-referentiel"


def collecte_docs(chercheur):  # self,
    """
    collecte_docs present dans elastichal.py
    partie Celery retirée pour les tests.
    Collecte les notices liées à un chercheur actuellement (peut être les labos également sous peu?)
    À mettre à jour et renommer lorsque intégré dans le code.
    Le code a été séparé en modules afin de pouvoir gérer les erreurs plus facilement
    """
    idhal = chercheur["idhal"]
    #TODO: look hal.find_publication for full base list of keys
    docs = hal.find_publications(idhal, "authIdHal_s")
    # récupération de l'existant
    doc_param = esActions.scope_term_multi(
        [("idhal", chercheur["idhal"]), ('category', "notice-hal")])
    docsExistantes = es.search(index="test2", query=doc_param)
    docsExistantes = docsExistantes["hits"]["hits"]
    if len(docsExistantes) > 0:
        docsExistantes = docsExistantes["hits"]["hits"][0]
        docsExistantes = docsExistantes["_source"]
        IddocsExistantes = [truc['docid'] for truc in docsExistantes]
    else:
        docsExistantes = []
        IddocsExistantes = []
    # Insert documents collection

    for num, doc in enumerate(docs):
        # L'id du doc est associé à celui du chercheur dans ES
        # Chaque chercheur ses docs
        # ci après c'est supposé que ce sont des chaines de caractère. Il me semble qu'on avait eu des soucis !!!
        # doc["_id"] = doc["docid"] + '_' + chercheur["idhal"] #c'est son doc à lui. Pourront être rajoutés ses choix de mots clés etc
        # supression des références au _id : laissons elastic gérer. On utilise le docid du doc. l'idhal du chercheur
        changements = False
        if doc["docid"] in IddocsExistantes:
            doc["MDS"] = utils.calculate_mds(doc)
            #
            if doc["MDS"] != [docAncien["MDS"] for docAncien in docsExistantes if
                              docAncien["_id"] == doc["_id"]][0]:
                # SI le MDS a changé alors modif qualitative sur la notice
                changements = True
            else:
                doc = [docAncien for docAncien in docsExistantes if docAncien["_id"] == doc["_id"]][
                    0]
        if doc["docid"] not in IddocsExistantes or changements:
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
            doc["Created"] = datetime.datetime.now().isoformat()
        if doc["docid"] not in IddocsExistantes:
            doc["harvested_from"] = "researcher"  # inutile je pense
            doc[
                "harvested_from_ids"] = []  # du coup çà devient inutile car présent dans le docId Mais ...
            doc["harvested_from_label"] = []  # idem ce champ serait à virer
            doc["harvested_from_ids"].append(chercheur["idhal"])  # idem ici
            doc["records"] = []
            doc["category"] = "notice-hal"
            doc["idhal"] = idhal,  # l'Astuce du
        else:
            pass

        # on recalcule à chaque collecte... pour màj
        doc["postprint_embargo"], doc["preprint_embargo"] = should_be_open(doc)

    # IddocsExistantes = [doc["_id"] for doc in docs]
    # searcher_data["liaison"]["travaux"]["hal"] = IddocsExistantes
    for doc in docs:
        # liaison du doc avec le chercheur INUTILE
        # doc ['profil'] = dict()
        # doc ['profil'] ['name'] = "hal"
        # TODO: utiliser le bulk en commentaires un peu plus haut car suppression du besoin de gérer le _id
        # indexation
        es.options(request_timeout=200, retry_on_timeout=True, max_retries=5).index(refresh=True,
                                                                                    routing=1,
                                                                                    # pour contrôler la propagation du lien de parenté
                                                                                    index="test2",
                                                                                    document=doc)  # ici par rapport au bulk on force l'id du doc indexé ES comme étant celui du doc.
    # Mise à jour du chercheur
    # es.update( index="test2", id=searcher_data ['halId_s'], document=searcher_data)
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

def scope_all():
    """
    Paramètre pour les requêtes ElasticSearch, retourne tous les documents
    """
    scope = {"match_all": {}}
    return scope


if __name__ == "__main__":
    index_list = ["researchers", "publications", "laboratories", "institutions", "expertises"]
    docmap = test_static.test_docmap2()
    if not es.indices.exists(index=f"test2"):
        es.indices.create(index=f"test2", mappings=docmap)
    # création d'un référentiel des domaines (ex concepts. On les appelle plus comme çà !!!)
    if not es.indices.exists(index=f"domaines-hal-referentiel"):
        es.indices.create(index=f"domaines-hal-referentiel", mappings=docmap)
    # Faudra sur le même modèle rajouter les labos et les structures.
    # Cela permet de générer autant d'axes ou sous groupes que nécessaires ;-)
    create_test_context()
    #
    print("#################################")
    print("Tests : trouver un chercheur")
    scope_searcher = esActions.scope_match_multi(
        [("idhal", "david-reymond"), ('category', "searcher")])
    cpt = es.count(index="test2", query=scope_searcher)['count']
    print("normalement 1 doc :", cpt)
    gugusse = es.search(index="test2", query=scope_searcher, size=cpt)["hits"]["hits"]
    for gu in gugusse:
        print(gu)
    print("#################################")
    print("Tests : trouver les notices d'un chercheur")

    scope_notices = esActions.scope_match_multi(
        [("idhal", "david-reymond"), ('category', "notice-hal")])
    cpt = es.count(index="test2", query=scope_notices)['count']
    print("à ce jour 106 doc :", cpt)
    doc_gugusse = es.search(index="test2", query=scope_notices, size=cpt)["hits"]["hits"]
    for doc in doc_gugusse:
        print(doc)
    print("#################################")

    scope_exp = esActions.scope_match_multi([("idhal", "david-reymond"), ('category', "expertise")])
    cpt = es.count(index="test2", query=scope_exp)['count']

    exp_gugusse = es.search(index="test2", query=scope_exp, size=cpt)["hits"]["hits"]
    print(
        "normalement 10 docs (MAIS c'est pas bon cf. infra remarques sur les expertises (çà sort d'où ???) !!!",
        cpt)
    for exp in exp_gugusse:
        print(exp)
    print("#################################")