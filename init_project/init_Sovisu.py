import datetime
from elasticsearch import helpers

from elasticHal.libs import (
    doi_enrichissement,
    hal,
    keyword_enrichissement,
    location_docs,
    utils, )
from init_project import init_sovisu_static
from sovisuhal.libs import esActions, elastichal
from sovisuhal.viewsActions import idhal_checkout

es = esActions.es_connector()


def create_test_context():
    # Variables à automatiser plus tard
    idhal = "david-reymond"
    orcid = ""
    labo_accro = "IMSIC"  # TODO: Faire sauter cette clé, remplacer par systeme qui créé fiche labo par chercheur
    idref = "test"
    labhalid = "527028"
    ldapid = "dreymond"
    structid = "198307662"
    """end of temp values"""
    # remplissage index structures
    struct_idref = "031122337"  # UTLN IDREF

    structure_message = set_elastic_structures(struct_idref)
    print(structure_message)

    # remplissage index de reference concepts
    concepts_message = indexe_expertises()
    print(concepts_message)

    # remplissage index sovisu_searchers
    idhal_test = idhal_checkout(idhal)
    if idhal_test > 0:
        elastichal.indexe_chercheur(structid, ldapid, labo_accro, labhalid, idhal, idref, orcid)

    # remplissage des publications
    # scope_param = scope_p("idhal", researcher_id) # ne renvoit rien, idhal est le bon champ
    # On retrouve le chercheur
    scope_param = esActions.scope_term_multi([("idhal", idhal), ('sovisu_category', "searcher")])
    chercheur = es.search(index="sovisu_searchers", query=scope_param)
    chercheur = chercheur["hits"]["hits"][0]["_source"]

    # à ce stade, chercheur contient des trucs inutiles : concepts et profil (ce dernier est là pour test modèle en arborescence (parent-child)
    print(chercheur)
    # collecte et indexation des docs
    publications_message = collecte_docs(chercheur)
    print(publications_message)

    # Remplissage de l'index sovisu_laboratories



def set_elastic_structures(search_value):
    if not es.indices.exists(index="structures_directory"):
        es.indices.create(index="structures_directory", mappings=init_sovisu_static.structures_mapping())

    search_filter = "idref_s"
    struct_type = "*"

    # Get the structure that match the given idref
    structures_entities = hal.find_structures_entities(search_filter, search_value, struct_type)

    child_filter = "parentIdref_s"
    # Get the children of the structure that match the given idref
    child_entities = hal.find_structures_entities(child_filter, search_value, struct_type)

    structures_entities.extend(child_entities)

    for structure in structures_entities:
        structure["_id"] = structure["docid"]

    helpers.bulk(es, structures_entities, index="structures_directory", refresh="wait_for")

    return f"{len(structures_entities)} structures added"


def creeFiche(dom, par):
    fiche = dict()
    fiche['chemin'] = "domAurehal." + dom[
        'id']  # .replace('.',',')  # donnera le chemin d'accès de l'arborescence. i.e: chercher .shs

    # https://www.mongodb.com/docs/manual/tutorial/model-tree-structures-with-materialized-paths/

    fiche['label_en'] = dom['label_en']
    fiche['label_fr'] = dom['label_fr']
    fiche["sovisu_category"] = "expertise"
    fiche["sovisu_referentiel"] = "hal"
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
    """Les compétences issues d'Aurehal sont indexées en tant que document dans l'index domaine_hal_referentiel.
      Les chercheurs valident ou pas celle issues de HAL, en rajoutent éventuellement. Cette action, copie la fiche
      et l'estampille à son idhal.
    """
    concept_list = GenereReferentiel(init_sovisu_static.concepts(), "")

    res = helpers.bulk(es, concept_list, index="domaine_hal_referentiel", refresh="wait_for")
    return str(res[0]), " Concepts added, in index domaine_hal_referentiel"


def collecte_docs(chercheur):  # self, # TODO: Revoir la méthode de verification des documents existants
    """
    collecte_docs present dans elastichal.py
    partie Celery retirée pour les tests.
    Collecte les notices liées à un chercheur actuellement (peut être les labos également sous peu?)
    À mettre à jour et renommer lorsque intégré dans le code.
    Le code a été séparé en modules afin de pouvoir gérer les erreurs plus facilement
    """
    idhal = chercheur["idhal"]
    # TODO: look hal.find_publication for full base list of keys
    docs = hal.find_publications(idhal, "authIdHal_s")
    # récupération de l'existant
    doc_param = esActions.scope_term_multi(
        [("idhal", chercheur["idhal"]), ('sovisu_category', "notice")])
    docsExistantes = es.search(index="sovisu_searchers", query=doc_param)
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
                doc = [docAncien for docAncien in docsExistantes if docAncien["_id"] == doc["_id"]][0]

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
            doc["MDS"] = utils.calculate_mds(doc)
            doc["Created"] = datetime.datetime.now().isoformat()
        if doc["docid"] not in IddocsExistantes:
            doc["harvested_from"] = "researcher"  # inutile je pense
            doc["harvested_from_ids"] = []  # du coup çà devient inutile car présent dans le docId Mais ...
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

        # on recalcule à chaque collecte... pour màj
        doc["postprint_embargo"], doc["preprint_embargo"] = elastichal.should_be_open(doc)

    helpers.bulk(es, docs, index="sovisu_searchers", refresh="wait_for")

    return "add publications done"

# Elasticsearch queries
# the queries under are different from those already registered,
# and follow this deprecation worning: https://github.com/elastic/elasticsearch-py/issues/1698


if __name__ == "__main__":

    index_mapping = {
        "sovisu_searchers": init_sovisu_static.document_mapping(),
        "sovisu_laboratories": init_sovisu_static.document_mapping(),
        "domaine_hal_referentiel": init_sovisu_static.expertises_mapping(),
        "structures_directory": init_sovisu_static.structures_mapping(),
    }
    for index, mapping_func in index_mapping.items():
        if not es.indices.exists(index=index):
            es.indices.create(index=index, mappings=mapping_func)

    # Faudra sur le même modèle rajouter les labos et les structures.
    # Cela permet de générer autant d'axes ou sous groupes que nécessaires ;-)
    create_test_context()
    # #
    # print("#################################")
    # print("Tests : trouver un chercheur")
    # scope_searcher = esActions.scope_match_multi(
    #     [("idhal", "david-reymond"), ('category', "searcher")])
    # cpt = es.count(index="sovisu_searchers", query=scope_searcher)['count']
    # print("normalement 1 doc :", cpt)
    # gugusse = es.search(index="sovisu_searchers", query=scope_searcher, size=cpt)["hits"]["hits"]
    # for gu in gugusse:
    #     print(gu)
    # print("#################################")
    # print("Tests : trouver les notices d'un chercheur")
    #
    # scope_notices = esActions.scope_match_multi(
    #     [("idhal", "david-reymond"), ('category', "notice")])
    # cpt = es.count(index="sovisu_searchers", query=scope_notices)['count']
    # print("à ce jour 106 doc :", cpt)
    # doc_gugusse = es.search(index="sovisu_searchers", query=scope_notices, size=cpt)["hits"]["hits"]
    # for doc in doc_gugusse:
    #     print(doc)
    # print("#################################")
    #
    # scope_exp = esActions.scope_match_multi([("idhal", "david-reymond"), ('category', "expertise")])
    # cpt = es.count(index="sovisu_searchers", query=scope_exp)['count']
    #
    # exp_gugusse = es.search(index="sovisu_searchers", query=scope_exp, size=cpt)["hits"]["hits"]
    # print(
    #     "normalement 10 docs (MAIS c'est pas bon cf. infra remarques sur les expertises (çà sort d'où ???) !!!",
    #     cpt)
    # for exp in exp_gugusse:
    #     print(exp)
    # print("#################################")
