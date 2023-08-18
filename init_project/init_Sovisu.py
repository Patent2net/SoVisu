import datetime
from elasticsearch import helpers

from elasticHal.libs import (
    doi_enrichissement,
    hal,
    keyword_enrichissement,
    location_docs,
    utils, )
from init_project import init_sovisu_static
from sovisuhal.libs import esActions
from sovisuhal.libs.elastichal import should_be_open, indexe_chercheur
from sovisuhal.viewsActions import idhal_checkout

# Import constants
from constants import SV_INDEX, SV_HAL_REFERENCES, SV_STRUCTURES_REFERENCES, SV_LAB_INDEX, TIMEZONE

es = esActions.es_connector()


def create_test_context():
    # Variables à automatiser plus tard
    idhal = "david-reymond"
    orcid = ""
    # TODO: Faire sauter labo_accro, remplacer par systeme qui créé fiche labo par chercheur
    labo_accro = "IMSIC"
    idref = "test"
    labhalid = "527028"
    ldapid = "dreymond"
    structid = "198307662"
    # remplissage index structures
    struct_idref = "031122337"  # UTLN IDREF

    create_elastic_index()

    # TODO: est il utile de garde l'index structure_directory? (referentiel des structures)
    structure_referential_message = set_structures_referential(struct_idref)
    print(structure_referential_message)

    structure_index_message = set_structure_index(struct_idref)
    print(structure_index_message)

    # remplissage index de reference concepts
    concepts_message = indexe_expertises()
    print(concepts_message)

    # remplissage index sovisu_searchers
    idhal_test = idhal_checkout(idhal)
    if idhal_test > 0:
        indexe_chercheur(structid, ldapid, labo_accro, labhalid, idhal, idref, orcid)

    # remplissage des publications
    # scope_param = scope_p("idhal", researcher_id) # ne renvoit rien, idhal est le bon champ
    # On retrouve le chercheur

    chercheur = es.get(index=SV_INDEX, id=idhal)
    chercheur = chercheur["_source"]
    print("______________")
    print(chercheur)
    # collecte et indexation des docs
    publications_message = collecte_docs(chercheur)
    print(publications_message)

    # Remplissage de l'index sovisu_laboratories


def create_elastic_index():
    index_mapping = {
        SV_INDEX: init_sovisu_static.document_mapping(),
        SV_LAB_INDEX: init_sovisu_static.document_mapping(),
        SV_HAL_REFERENCES: init_sovisu_static.expertises_mapping(),
        SV_STRUCTURES_REFERENCES: init_sovisu_static.structures_mapping(),
    }
    for index, mapping_func in index_mapping.items():
        if not es.indices.exists(index=index):
            es.indices.create(index=index, mappings=mapping_func)


def get_elastic_structures(search_value):

    search_filter = "idref_s"
    struct_type = "*"

    # Get the structure that match the given idref
    structures_entities = hal.find_structures_entities(search_filter, search_value, struct_type)

    child_filter = "parentIdref_s"
    # Get the children of the structure that match the given idref
    child_entities = hal.find_structures_entities(child_filter, search_value, struct_type)

    structures_entities.extend(child_entities)

    return structures_entities


def set_structures_referential(search_value):

    structures_entities = get_elastic_structures(search_value)

    for structure in structures_entities:
        structure["_id"] = structure["docid"]

    helpers.bulk(es, structures_entities, index=SV_STRUCTURES_REFERENCES, refresh="wait_for")

    return f"{len(structures_entities)} structures added in {SV_STRUCTURES_REFERENCES} index"


def set_structure_index(search_value):
    structures_entities = get_elastic_structures(search_value)
    
    for structure in structures_entities:
        structure["_id"] = structure["docid"]
        structure["sv_parent_type"] = "structure"

    helpers.bulk(es, structures_entities, index=SV_LAB_INDEX, refresh="wait_for")

    return f"{len(structures_entities)} structures added in {SV_LAB_INDEX} index"

def creeFiche(dom):  # placée dans elasticHal.utils
    fiche = dict()
    fiche['chemin'] = "domAurehal." + dom['id']
    # .replace('.',',')  # donnera le chemin d'accès de l'arborescence. i.e: chercher .shs

    # https://www.mongodb.com/docs/manual/tutorial/model-tree-structures-with-materialized-paths/

    fiche['label_en'] = dom['label_en']
    fiche['label_fr'] = dom['label_fr']
    fiche["sovisu_category"] = "expertise"
    fiche["sovisu_referentiel"] = "hal"
    fiche["_id"] = fiche["chemin"]
    return fiche


def GenereReferentiel(arbre, par):
    # TODO: utiliser l'API https://api.archives-ouvertes.fr/ref/domain/?q=*&wt=json&fl=*
    fiches = []
    if isinstance(arbre, list):
        for dom in arbre:
            if "children" in dom.keys():
                # {'id': 'chim.anal', 'label_en': 'Analytical chemistry', 'label_fr': 'Chimie analytique', 'children': []}
                if len(dom['children']) != 0:
                    fiches.append(creeFiche(dom))
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
                fiches.append(creeFiche(dom))
    else:
        fiches.append(creeFiche(arbre))
        if "children" in arbre.keys():
            # {'id': 'chim.anal', 'label_en': 'Analytical chemistry', 'label_fr': 'Chimie analytique', 'children': []}
            if len(arbre['children']) != 0:
                fiches.append(creeFiche(arbre))
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
    """Les compétences issues d'Aurehal sont indexées en tant que document
    dans l'index domaine_hal_referentiel.
    Les chercheurs valident ou pas celle issues de HAL, en rajoutent éventuellement. Cette action,
    copie la fiche et l'estampille à son idhal.
    """
    concept_list = GenereReferentiel(init_sovisu_static.concepts(), "")

    res = helpers.bulk(es, concept_list, index=SV_HAL_REFERENCES, refresh="wait_for")
    return str(res[0]), " Concepts added, in index domaine_hal_referentiel"


def collecte_docs(chercheur):  # self,
    """
    collecte_docs present dans elastichal.py
    partie Celery retirée pour les tests.
    Collecte les notices liées à un chercheur actuellement (peut être les labos également sous peu?)
    À mettre à jour et renommer lorsque intégré dans le code.
    Le code a été séparé en modules afin de pouvoir gérer les erreurs plus facilement
    """
    # doc_progress_recorder = ProgressRecorder(self)
    new_documents = []
    idhal = chercheur["idhal"]
    # look hal.find_publication for full base list of keys
    docs = hal.find_publications(idhal, "authIdHal_s")

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
        # doc_progress_recorder.set_progress(num,len(docs), str(num) + " sur " + str(len(docs)) + " documents")

    for indi in range(int(len(new_documents) // 50) + 1):
        boutdeDoc = new_documents[indi * 50: indi * 50 + 50]
        helpers.bulk(
            es,
            boutdeDoc,
            index=SV_INDEX,
        )

    # doc_progress_recorder.set_progress( num, len(docs), str(num) + " sur " + str(len(docs)) + " indexés")
    return "add publications done"


# Elasticsearch queries
# the queries under are different from those already registered,
# and follow this deprecation worning: https://github.com/elastic/elasticsearch-py/issues/1698


if __name__ == "__main__":

    # Faudra sur le même modèle rajouter les labos et les structures.
    # Cela permet de générer autant d'axes ou sous groupes que nécessaires ;-)
    create_test_context()
