import datetime
import time
from decouple import config
# Celery
from celery import shared_task

# Celery-progress
from celery_progress.backend import ProgressRecorder
from elasticsearch import helpers

from elasticHal.libs import (
    doi_enrichissement,
    hal,
    keyword_enrichissement,
    location_docs,
    utils,
)
from elasticHal.models import Laboratory, Researcher

# Custom libs
from sovisuhal.libs import esActions

# Global variables
structIdlist = None

# if True, check all the existing data in ES index
# to compare with those gathered to keep part of totality of data persistence
check_existing_docs = eval(config("VerifieExistant"))

# if True, overwrite the doc['validated'] status
# to True for all the docs existing in ES (work only if Check_existing_docs = True)
force_doc_validated = eval(config("ForceValidation"))

# if True, overwrite the doc["authorship"] status
# for all the docs existing in ES (work only if Check_existing_docs = True)
force_doc_authorship =eval(config("ForceAutorat"))


# If djangodb_open = True script will use django Db to generate index for ES.
# Default Value is False vhen used as a script and True when called by SoVisu.
# (check the code at the bottom of the file)
djangodb_open = None


harvet_history = []

# Connect to DB
es = esActions.es_connector()
# get structId for already existing structures in ES
scope_param = esActions.scope_all()


def get_structid_list():
    """
    Récupère la liste des structSirene des structures recensées dans ElasticSearch
    """
    global structIdlist
    structIdlist = []
    res = es.search(
        index="*-structures",
        body=scope_param,
        filter_path=["hits.hits._source.structSirene"],
        request_timeout=50,
    )
    print(res)
    if res:
        structIdlist = [hit["_source"]["structSirene"] for hit in res["hits"]["hits"]]
    # print("\u00A0 \u21D2 ", structIdlist)
    return structIdlist


@shared_task(bind=True)
def collect_laboratories_data2(self, labo, update=True):
    """
    Collecte les données de laboratoires depuis HAL et les enregistre dans ElasticSearch.
    Paramètre update non utilisé mais appelé dans une fonction admin
    """
    # Init laboratories
    laboratories_list = []
    # progress_recorder = ProgressRecorder(self)
    doc_progress_recorder = ProgressRecorder(self)
    # init es_laboratories
    count = es.count(index="*-laboratories", body=scope_param, request_timeout=50)["count"]
    # progress_recorder.set_progress(0, count, " labo traités ")
    if count > 0:
        # grosse feint, on ne récupère que le labo coché
        # print("\u00A0 \u21D2", count, "laboratories found in ES, checking es_laboratories list")
        res = es.search(index="*-laboratories", body=scope_param, size=count, request_timeout=50)
        es_laboratories = res["hits"]["hits"]
        for lab in es_laboratories:
            if labo == lab["_source"]["halStructId"]:
                laboratories_list.append(lab["_source"])

    if djangodb_open:
        djangolab = Laboratory.objects.all().values()
        [lab.pop("id") for lab in djangolab]
        if laboratories_list:
            for lab in djangolab:
                if any(
                    dictlist["halStructId"] != lab["halStructId"] for dictlist in laboratories_list
                ):
                    laboratories_list.append(lab)
        else:
            laboratories_list = djangolab

    # print(f'laboratories_list values = {laboratories_list}')
    # Process laboratories
    nblab = 0
    collections_set = set([lab["halStructId"] for lab in laboratories_list])

    for col in collections_set:
        labor =  [lab for lab in laboratories_list if lab["halStructId"] == col]
        lab = labor[0]
        # print(f"\u00A0 \u21D2 Processing : {lab['acronym']}")
        # progress_recorder.set_progress( nblab, count, lab['acronym'] + " labo en cours")
        nblab += 1
        # Collect publications
        if len(lab["halStructId"]) >0:
            docs = hal.find_publications(lab["halStructId"], "labStructId_i")

            # Insert documents collection
            if isinstance(docs, list):
                if len(docs) > 1:
                    for num, doc in enumerate(docs):
                        doc_progress_recorder.set_progress(
                            num,
                            len(docs),
                            "Collection "
                            + lab["acronym"]
                            + " en cours. docid : "
                            + str(doc["docid"]),
                        )
                        # Enrichissements des documents récoltés
                        doc["country_origin"] = location_docs.generate_countrys_fields(doc)
                        doc = doi_enrichissement.docs_enrichissement_doi(doc)

                        # lstResum = [cle for cle in doc.keys() if "abstract" in cle]
                        # for cle in lstResum: # est-ce utile ?????
                        #     if isinstance(doc[cle], list):
                        #         doc[cle] = " ".join(doc[cle])
                        #     else:
                        #         pass
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
                        doc["validated"] = True
                        doc["harvested_from"] = "lab"
                        doc["harvested_from_ids"] = []

                        doc["harvested_from_ids"].append(lab["halStructId"])
                        doc["harvested_from_label"] = []
                        doc["harvested_from_label"].append(lab["acronym"])
                        if "Created" not in doc:
                            doc["Created"] = datetime.datetime.now().isoformat()

                        doc["authorship"] = []

                        # MISE EN COMMENTAIRE
                        # l'autorat se définit : est-ce que l'un des membres du labo est 1er auteur
                        # --> first
                        # ou  est-ce que l'un des membres du labo est dernier auteur
                        # --> last
                        #
                        # je ne pense pas que ce puisse être calculé ici
                        # mais seulement lorsque tous les membres du lab on collecté et calculé
                        # leur autorat
                        #
                        # authid_s_filled = []
                        # if "authId_i" in doc:
                        #     for auth in doc["authId_i"]:
                        #         if len(auth.strip()) >0:
                        #             try:
                        #                 aurehal = archivesOuvertes.get_halid_s(auth)
                        # pourquoi on va chercher l'auréhal de chaque auteur ???
                        #                 authid_s_filled.append(aurehal)
                        #             except:
                        #                 authid_s_filled.append("")
                        # else:
                        #     print("des docs sans auteurs ?????")
                        # authors_count = len(authid_s_filled)
                        # i = 0
                        # for auth in authid_s_filled:
                        # d'autant que pour chaque auteur qui a pas d'aurehal
                        # çà va foirer la numérotation (passer en 1er auteur si aucun aurehal avant)
                        #     i += 1
                        #     if i == 1 and auth != "":
                        #         doc["authorship"].append(
                        #             {
                        #                 "authorship": "firstAuthor",
                        #                 "authFullName_s": auth,
                        #             }
                        #         )
                        #     elif i == authors_count and auth != "":
                        #         doc["authorship"].append(
                        #             {"authorship": "lastAuthor", "authFullName_s": auth}
                        #         )

                        # d'autant que j'aurais fait comme çà : cf.

                        doc["harvested_from_ids"] = [labo]

                        doc["MDS"] = utils.calculate_mds(doc)
                        doc["records"] = []

                        try:
                            should_be_open = utils.should_be_open(doc)
                            if should_be_open == 1:
                                doc["should_be_open"] = True
                            if should_be_open == -1:
                                doc["should_be_open"] = False

                            if should_be_open == 1 or should_be_open == 2:
                                doc["isOaExtra"] = True
                            elif should_be_open == -1:
                                doc["isOaExtra"] = False
                        except IndexError:
                            print("publicationDate_tdate error ?")

                    for lab in labor:
                        if check_existing_docs:
                            for doc in docs:
                                doc_param = esActions.scope_p("_id", doc["_id"])
                                if not es.indices.exists(
                                    index=lab["structSirene"]
                                    + "-"
                                    + lab["halStructId"]
                                    + "-laboratories-documents"
                                ):
                                    es.indices.create(
                                        index=lab["structSirene"]
                                        + "-"
                                        + lab["halStructId"]
                                        + "-laboratories-documents"
                                    )
                                    res = es.search(
                                        index=lab["structSirene"]
                                        + "-"
                                        + lab["halStructId"]
                                        + "-laboratories-documents",
                                        body=doc_param,
                                        request_timeout=50,
                                )

                                if len(res["hits"]["hits"]) > 0:
                                    if (
                                        "authorship" in res["hits"]["hits"][0]["_source"]
                                        and not force_doc_authorship
                                    ):
                                        doc["authorship"] = res["hits"]["hits"][0]["_source"][
                                            "authorship"
                                        ]
                                    if "validated" in res["hits"]["hits"][0]["_source"]:
                                        doc["validated"] = res["hits"]["hits"][0]["_source"][
                                            "validated"
                                        ]
                                    if force_doc_validated:
                                        doc["validated"] = True

                                    if "modifiedDate_tdate" in res["hits"]["hits"][0]["_source"].keys():
                                        if res["hits"]["hits"][0]["_source"]["modifiedDate_tdate"]!= doc["modifiedDate_tdate"]:
                                            doc["records"].append(
                                                {
                                                    "beforeModifiedDate_tdate": doc["modifiedDate_tdate"],
                                                    "MDS": res["hits"]["hits"][0]["_source"]["MDS"],
                                                }
                                            )
                                    else:
                                        pass #
                                else:
                                    doc["validated"] = True

                        for indi in range(int(len(docs) // 50) + 1):
                            boutdeDoc = docs[indi * 50 : indi * 50 + 50]
                            helpers.bulk(
                                es,
                                boutdeDoc,
                                index=lab["structSirene"]
                                + "-"
                                + lab["halStructId"]
                                + "-laboratories-documents",
                            )
                            #time.sleep(1)
                            doc_progress_recorder.set_progress(
                                (indi + 1) * 50,
                                len(docs),
                                lab["acronym"] + " " + str(len(docs)) + " documents",
                            )
            else:
                doc_progress_recorder.set_progress(
                     nblab, len(laboratories_list), lab["acronym"] + " " + " Pas de documents"
                )
        # progress_recorder.set_progress(nblab, count, lab['acronym'] + " labo traité")

    return "finished"


@shared_task(bind=True)
def collect_researchers_data(self, struct):
    """
    Collecte des données des chercheurs sur HAL et les enregistre dans ElasticSearch
    """
    # initialisation liste labos supposée plus fiables que données issues Ldap.
    progress_recorder = ProgressRecorder(self)
    #doc_progress_recorder = ProgressRecorder(self)
    labos, dico_acronym = init_labo()
    print(f"\u00A0 \u21D2 labos values ={labos}")
    print(f"\u00A0 \u21D2 dicoAcronym values ={dico_acronym}")
    # Init researchers
    researchers_list = []

    count = es.count(index=struct + "*-researchers", body=scope_param, request_timeout=50)["count"]
    if count > 0:
        # print(
        #     "\u00A0 \u21D2 ",
        #     count,
        #     " researchers found in ES, checking es_researchers list",
        # )
        res = es.search(
            index=struct + "*-researchers",
            body=scope_param,
            size=count,
            request_timeout=50,
        )
        es_researchers = res["hits"]["hits"]
        for searcher in es_researchers:
            researchers_list.append(searcher["_source"])

    if djangodb_open:
        django_researchers = Researcher.objects.all().values()
        django_researchers = [
            researcher
            for researcher in django_researchers
            if researcher["halId_s"] != "" and researcher.pop("id")
        ]  # Only keep researchers with known 'halId_s' and remove the 'id' value created by Django_DB
        if len(researchers_list) >0:
            print("checking DjangoDb laboratory list:")
            for searcher in django_researchers:
                if any(dictlist["halId_s"] != searcher["halId_s"] for dictlist in researchers_list):
                    researchers_list.append(searcher)
        else:
            researchers_list = django_researchers

    # print(f'\u00A0 \u21D2 researchers_list content = {researchers_list}')
    # Process researchers
    j = 1
    for searcher in researchers_list:
        progress_recorder.set_progress(j, count, " chercheurs traités ")
        j = j + 1
        if searcher["structSirene"] == struct:  # seulement les chercheurs de la structure
            # print(f"\u00A0 \u21D2 Processing : {searcher['halId_s']}")
            if searcher["labHalId"] not in labos:
                searcher["labHalId"] = "non-labo"
            # Collect publications

            docs = hal.find_publications(searcher["halId_s"], "authIdHal_s")
            # Enrichssements des documents récoltés

            # Insert documents collection
            if isinstance(docs, list):
                if len(docs) > 1:
                    for num, doc in enumerate(docs):
                        if num > 1:
                            progress_recorder.set_progress(
                                num,
                                len(docs),
                                " documents traités pour idhal :" + searcher["halId_s"],
                            )
                        else:
                            progress_recorder.set_progress(
                                num,
                                len(docs),
                                " documents traités pour idhal : " + searcher["halId_s"],
                            )
                        doc["country_colaboration"] = location_docs.generate_countrys_fields(doc)
                        doc = doi_enrichissement.docs_enrichissement_doi(doc)
                        if "fr_abstract_s" in doc.keys():
                            if isinstance(doc["fr_abstract_s"], list):
                                doc["fr_abstract_s"] = "/n".join(doc["fr_abstract_s"])
                            if len(doc["fr_abstract_s"]) > 100:
                                try:
                                    doc["fr_entites"] = keyword_enrichissement.return_entities(
                                        doc["fr_abstract_s"], "fr"
                                    )
                                except IndexError:
                                    doc["fr_entites"] = []
                                try:
                                    doc[
                                        "fr_teeft_keywords"
                                    ] = keyword_enrichissement.keyword_from_teeft(
                                        doc["fr_abstract_s"], "fr"
                                    )
                                except IndexError:
                                    doc["fr_teeft_keywords"] = []
                        if "en_abstract_s" in doc.keys():
                            if isinstance(doc["en_abstract_s"], list):
                                doc["en_abstract_s"] = "/n".join(doc["en_abstract_s"])
                            if len(doc["en_abstract_s"]) > 100:
                                try:
                                    doc["en_entites"] = keyword_enrichissement.return_entities(
                                        doc["en_abstract_s"], "en"
                                    )
                                except IndexError:
                                    doc["en_entites"] = []
                                try:
                                    doc[
                                        "en_teeft_keywords"
                                    ] = keyword_enrichissement.keyword_from_teeft(
                                        doc["en_abstract_s"], "en"
                                    )
                                except IndexError:
                                    doc["en_teeft_keywords"] = []
                        doc["_id"] = doc["docid"]
                        doc["validated"] = True

                        doc["harvested_from"] = "researcher"

                        doc["harvested_from_ids"] = []
                        doc["harvested_from_label"] = []
                        try:
                            doc["harvested_from_label"].append(dico_acronym[searcher["labHalId"]])
                        except IndexError:
                            doc["harvested_from_label"].append("non-labo")

                        doc["authorship"] = []

                        # if "authIdHal_s" in doc:
                        #     authors_count = len(doc["authIdHal_s"])
                        #     i = 0
                        #     for auth in doc["authIdHal_s"]:
                        #         i += 1
                        #         if i == 1:
                        #             doc["authorship"].append(
                        #                 {"authorship": "firstAuthor", "halId_s": auth}
                        #             )
                        #         elif i == authors_count:
                        #             doc["authorship"].append(
                        #                 {"authorship": "lastAuthor", "halId_s": auth}
                        #             )
                        if "Created" not in doc:
                            doc["Created"] = datetime.datetime.now().isoformat()

                        doc["harvested_from_ids"].append(searcher["halId_s"])
                        # historique d'appartenance du docId
                        # pour attribuer les bons docs aux chercheurs
                        harvet_history.append({"docid": doc["docid"], "from": searcher["halId_s"]})

                        for h in harvet_history:
                            if h["docid"] == doc["docid"]:
                                if h["from"] not in doc["harvested_from_ids"]:
                                    doc["harvested_from_ids"].append(h["from"])

                        doc["records"] = []
                        doc["MDS"] = utils.calculate_mds(doc)

                        try:
                            should_be_open = utils.should_be_open(doc)
                            if should_be_open == 1:
                                doc["should_be_open"] = True
                            if should_be_open == -1:
                                doc["should_be_open"] = False

                            if should_be_open == 1 or should_be_open == 2:
                                doc["isOaExtra"] = True
                            elif should_be_open == -1:
                                doc["isOaExtra"] = False
                        except IndexError:
                            print("publicationDate_tdate error ?")

                        if check_existing_docs:
                            doc_param = esActions.scope_p("_id", doc["_id"])

                            if not es.indices.exists(
                                index=searcher["structSirene"]
                                + "-"
                                + searcher["labHalId"]
                                + "-researchers-"
                                + searcher["ldapId"]
                                + "-documents"
                            ):  # -researchers" + searcher["ldapId"] + "-documents
                                print(f'exception {searcher["labHalId"]}, {searcher["ldapId"]}')
                                res = dict()
                                res["hits"] = dict()
                                res["hits"]["hits"] = []
                            else:
                                res = es.search(
                                    index=searcher["structSirene"]
                                    + "-"
                                    + searcher["labHalId"]
                                    + "-researchers-"
                                    + searcher["ldapId"]
                                    + "-documents",
                                    body=doc_param,
                                    request_timeout=50,
                                )  # -researchers" + searcher["ldapId"] + "-documents

                            if len(res["hits"]["hits"]) > 0:
                                if (
                                    "authorship" in res["hits"]["hits"][0]["_source"]
                                    and not force_doc_authorship
                                ):
                                    doc["authorship"] = res["hits"]["hits"][0]["_source"][
                                        "authorship"
                                    ]
                                if "validated" in res["hits"]["hits"][0]["_source"]:
                                    doc["validated"] = res["hits"]["hits"][0]["_source"][
                                        "validated"
                                    ]
                                if force_doc_validated:
                                    doc["validated"] = True

                                if (
                                    res["hits"]["hits"][0]["_source"]["modifiedDate_tdate"]
                                    != doc["modifiedDate_tdate"]
                                ):
                                    doc["records"].append(
                                        {
                                            "beforeModifiedDate_tdate": doc["modifiedDate_tdate"],
                                            "MDS": res["hits"]["hits"][0]["_source"]["MDS"],
                                        }
                                    )

                            else:
                                doc["validated"] = True
                    for indi in range(int(len(docs) // 50) + 1):
                        boutdeDoc = docs[indi * 50 : indi * 50 + 50]
                        helpers.bulk(
                            es,
                            boutdeDoc,
                            request_timeout=100,
                            index=searcher["structSirene"]
                            + "-"
                            + searcher["labHalId"]
                            + "-researchers-"
                            + searcher["ldapId"]
                            + "-documents",
                            # -researchers" + searcher["ldapId"] + "-documents
                        )
                        print(str(len(boutdeDoc)) + " indexés " + searcher["ldapId"])
#                        time.sleep(1)

            else:
                progress_recorder.set_progress(0, 0, " pas de docs 1" + searcher["halId_s"])
        else:
            print(
                "\u00A0 \u21D2 chercheur hors structure,"
                + f" {searcher['ldapId']}, structure : {searcher['structSirene']}"
            )

    progress_recorder.set_progress(100, 100, " fin traitements. ")
    progress_recorder.set_progress(count, count, " chercheurs traités ")
    return "finished"


@shared_task(bind=True)
def collect_laboratories_data(self):
    """
    Collecte les données des laboratoires dans HAL et les indexe dans ElasticSearch
    """
    # Init laboratories
    laboratories_list = []
    progress_recorder = ProgressRecorder(self)
    doc_progress_recorder = ProgressRecorder(self)
    # init es_laboratories
    count = es.count(index="*-laboratories", body=scope_param, request_timeout=50)["count"]
    progress_recorder.set_progress(0, count, " labo traités ")
    if count > 0:
        print(
            "\u00A0 \u21D2",
            count,
            " laboratories found in ES, checking es_laboratories list",
        )
        res = es.search(index="*-laboratories", body=scope_param, size=count, request_timeout=50)
        es_laboratories = res["hits"]["hits"]
        for lab in es_laboratories:
            laboratories_list.append(lab["_source"])

    if djangodb_open:
        djangolab = Laboratory.objects.all().values()
        [lab.pop("id") for lab in djangolab]
        if laboratories_list:
            print("\u00A0 \u21D2 checking DjangoDb laboratory list:")
            for lab in djangolab:
                if any(
                    dictlist["halStructId"] != lab["halStructId"] for dictlist in laboratories_list
                ):
                    laboratories_list.append(lab)
        else:
            laboratories_list = djangolab

    # Process laboratories
    nblab = 0
    for lab in laboratories_list:
        print(f"\u00A0 \u21D2 Processing : {lab['acronym']}")
        progress_recorder.set_progress(nblab, count, " labo " + str(lab["acronym"]) + " en cours")
        nblab += 1
        # Collect publications
        if len(lab["halStructId"]) > 0:
            docs = hal.find_publications(lab["halStructId"], "labStructId_i")

            # docs = doi_enrichissement.docs_enrichissement_doi(docs)
            # docs = keyword_enrichissement.keyword_from_teeft(docs)
            # docs = keyword_enrichissement.return_entities(docs)

            # Insert documents collection
            if isinstance(docs, list):
                if len(docs) > 1:
                    for num, doc in enumerate(docs):
                        doc_progress_recorder.set_progress(
                            num,
                            len(docs),
                            "Collection "
                            + lab["acronym"]
                            + " en cours. Docid: "
                            + str(doc["docid"]),
                        )
                        # print(f"- sub processing : {str(doc['docid'])}")
                        # Enrichssements des documents récoltés
                        doc["country_colaboration"] = location_docs.generate_countrys_fields(doc)
                        lstResum = [cle for cle in doc.keys() if "abstract" in cle]
                        for cle in lstResum:
                            if isinstance(doc[cle], list):
                                doc[cle] = " ".join(doc[cle])
                            else:
                                pass
                        doc["_id"] = doc["docid"]
                        doc["validated"] = True
                        doc["harvested_from"] = "lab"
                        doc["harvested_from_ids"] = []

                        doc["harvested_from_ids"].append(lab["halStructId"])
                        doc["harvested_from_label"] = []
                        doc["harvested_from_label"].append(lab["acronym"])
                        if "Created" not in doc:
                            doc["Created"] = datetime.datetime.now().isoformat()

                        doc["authorship"] = []

                        harvet_history.append({"docid": doc["docid"], "from": lab["halStructId"]})

                        for h in harvet_history:
                            if h["docid"] == doc["docid"]:
                                doc["harvested_from_ids"].append(h["from"])

                        doc["MDS"] = utils.calculate_mds(doc)
                        doc["records"] = []

                        try:
                            should_be_open = utils.should_be_open(doc)
                            if should_be_open == 1:
                                doc["should_be_open"] = True
                            if should_be_open == -1:
                                doc["should_be_open"] = False

                            if should_be_open == 1 or should_be_open == 2:
                                doc["isOaExtra"] = True
                            elif should_be_open == -1:
                                doc["isOaExtra"] = False
                        except IndexError:
                            print("publicationDate_tdate error ?")

                        if check_existing_docs:
                            doc_param = esActions.scope_p("_id", doc["_id"])

                            if not es.indices.exists(
                                index=lab["structSirene"]
                                + "-"
                                + lab["halStructId"]
                                + "-laboratories-documents"
                            ):
                                es.indices.create(
                                    index=lab["structSirene"]
                                    + "-"
                                    + lab["halStructId"]
                                    + "-laboratories-documents"
                                )
                            res = es.search(
                                index=lab["structSirene"]
                                + "-"
                                + lab["halStructId"]
                                + "-laboratories-documents",
                                body=doc_param,
                                request_timeout=50,
                            )

                            if len(res["hits"]["hits"]) > 0:
                                if (
                                    "authorship" in res["hits"]["hits"][0]["_source"]
                                    and not force_doc_authorship
                                ):
                                    doc["authorship"] = res["hits"]["hits"][0]["_source"][
                                        "authorship"
                                    ]
                                if "validated" in res["hits"]["hits"][0]["_source"]:
                                    doc["validated"] = res["hits"]["hits"][0]["_source"][
                                        "validated"
                                    ]
                                if force_doc_validated:
                                    doc["validated"] = True

                                if (
                                    res["hits"]["hits"][0]["_source"]["modifiedDate_tdate"]
                                    != doc["modifiedDate_tdate"]
                                ):
                                    doc["records"].append(
                                        {
                                            "beforeModifiedDate_tdate": doc["modifiedDate_tdate"],
                                            "MDS": res["hits"]["hits"][0]["_source"]["MDS"],
                                        }
                                    )
                            else:
                                doc["validated"] = True

                for indi in range(int(len(docs) // 50) + 1):
                    boutdeDoc = docs[indi * 50 : indi * 50 + 50]
                    helpers.bulk(
                        es,
                        boutdeDoc,
                        index=lab["structSirene"]
                        + "-"
                        + lab["halStructId"]
                        + "-laboratories-documents",
                    )
                    #time.sleep(1)
                    doc_progress_recorder.set_progress(
                        (indi + 1) * 50,
                        len(docs),
                        lab["acronym"] + " " + str(len(docs)) + " documents",
                    )
            else:
                doc_progress_recorder.set_progress(0, 0, " pas de docs 2" + lab["halStructId"])
        progress_recorder.set_progress(nblab, count, lab["acronym"] + " labo traité")

    return "finished"


def TrouveChercheurs(struct):
    # Init researchers
    researchers_list = []
    labos, dico_acronym = init_labo()
    count = 0
    es_researchers = []
    for lab in dico_acronym.keys():
        indexes = struct +"-"+ lab + "-researchers"
        if es.indices.exists(index=indexes):
            count += es.count(index=indexes, body=scope_param, request_timeout=50)["count"]
            if count > 0:
                res = es.search(index=indexes, body=scope_param, size=count, request_timeout=50)
                es_researchers .extend(res["hits"]["hits"])
    for searcher in es_researchers:
        researchers_list.append(searcher["_source"])
    return researchers_list

@shared_task(bind=True)
def collect_researchers_data2(self, struct, idx):
    """
    Collecte les données des chercheurs appartenant à un laboratoire,
    crée les index pour les chercheurs s'ils n'existent pas dans elasticsearch.
    """
    doc_progress_recorder = ProgressRecorder(self)
    labos, dico_acronym = init_labo()
    if idx =="":
        researchers_list = TrouveChercheurs(struct) # appelé sans index, collect_researchers_data2 trouve trous les chercheurs de la structure
    else:
        idxCher = idx.replace("laboratories", "researchers")
        researchers_list = []
        if es.indices.exists(index=idxCher):
            count = es.count(index=idxCher, body=scope_param, request_timeout=50)["count"]
            if count > 0:
                res = es.search(index=idxCher, body=scope_param, size=count, request_timeout=50)
                es_researchers  = res["hits"]["hits"]
                for searcher in es_researchers:
                  researchers_list.append(searcher["_source"])
            else:
                pass


    # Process researchers
    sommeDocs = 0
    count = len(researchers_list)

    for numCh, searcher in enumerate(researchers_list):
        #if numCh<1:
        # pourquoi ne pas lancer un collecte_doc ici ????
            doc_progress_recorder.set_progress(
            numCh, count, " chercheur traité (" + searcher["halId_s"] + ") dans " + struct)
            docs = hal.find_publications(searcher["halId_s"], "authIdHal_s")
            # Enrichissements des documents récoltés
            # print ("2e " + str(type (docs)))
            # Insert documents collection
            if isinstance(docs, list):
                # doc_progress_recorder.set_progress(k, len(docs),
                # " documents traités " + searcher["halId_s"])
                sommeDocs += len(docs)
                if len(docs) > 1:
                    for num, doc in enumerate(docs):
                        doc["country_colaboration"] = location_docs.generate_countrys_fields(doc)
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
                        doc["validated"] = True
                        doc["harvested_from"] = "researcher"
                        doc["harvested_from_ids"] = []
                        doc["harvested_from_label"] = []
                        try:
                            doc["harvested_from_label"].append(dico_acronym[searcher["labHalId"]])
                        except IndexError:
                            doc["harvested_from_label"].append("non-labo")
                        doc["authorship"] = []
                        # Pourquoi j'ai l'impression que c'est la 4e fois ce passage ???????
                        lstAut = [aut.title() for aut in doc["authLastName_s"]]
                        trouve = None
                        if searcher["lastName"].title() in lstAut:
                            trouve = searcher["lastName"].title()
                        else:
                            lstAut = [aut.title() for aut in doc["authFirstName_s"]]
                            if searcher["lastName"].title() in lstAut:
                                trouve = searcher["lastName"].title()
                        if trouve:
                            if lstAut.index(searcher["lastName"].title()) == 0:
                                doc["authorship"] = [
                                    {"authorship": "firstAuthor", "authIdHal_s": searcher["halId_s"]}
                                ]  # pas voulu casser le modele de données ici
                                # mais first, last ou rien suffirait non ?
                            elif (
                                lstAut.index(searcher["lastName"].title())
                                == len(doc["authLastName_s"]) - 1
                            ):
                                doc["authorship"] = [
                                    {"authorship": "lastAuthor", "authIdHal_s": searcher["halId_s"]}
                                ]
                        else:
                            doc["authorship"] = []
                        if "Created" not in doc:
                            doc["Created"] = datetime.datetime.now().isoformat()

                        doc["harvested_from_ids"].append(searcher["halId_s"])
                        # historique d'appartenance du docId
                        # pour attribuer les bons docs aux chercheurs
                        harvet_history.append({"docid": doc["docid"], "from": searcher["halId_s"]})

                        for h in harvet_history:
                            if h["docid"] == doc["docid"]:
                                if h["from"] not in doc["harvested_from_ids"]:
                                    doc["harvested_from_ids"].append(h["from"])

                        doc["records"] = []
                        doc["MDS"] = utils.calculate_mds(doc)
                        #####
                        # indexation sur index spécial
                        ####

                        #### Fin index spécial
                        try:
                            should_be_open = utils.should_be_open(doc)
                            if should_be_open == 1:
                                doc["should_be_open"] = True
                            if should_be_open == -1:
                                doc["should_be_open"] = False

                            if should_be_open == 1 or should_be_open == 2:
                                doc["isOaExtra"] = True
                            elif should_be_open == -1:
                                doc["isOaExtra"] = False
                        except IndexError:
                            print("publicationDate_tdate error ?")

                        if check_existing_docs:
                            doc_param = esActions.scope_p("_id", doc["_id"])

                            if not es.indices.exists(
                                index=searcher["structSirene"]
                                + "-"
                                + searcher["labHalId"]
                                + "-researchers-"
                                + searcher["ldapId"]
                                + "-documents"
                            ):  # -researchers" + searcher["ldapId"] + "-documents
                                #print(f'exception {searcher["labHalId"]}, {searcher["ldapId"]}')
                                res = dict()
                                res["hits"] = dict()
                                res["hits"]["hits"] = []
                            else:
                                res = es.search(
                                    index=searcher["structSirene"]
                                    + "-"
                                    + searcher["labHalId"]
                                    + "-researchers-"
                                    + searcher["ldapId"]
                                    + "-documents",
                                    body=doc_param,
                                    request_timeout=50,
                                )  # -researchers" + searcher["ldapId"] + "-documents

                            if len(res["hits"]["hits"]) > 0:
                                if (
                                    "authorship" in res["hits"]["hits"][0]["_source"]
                                    and not force_doc_authorship
                                ):
                                    doc["authorship"] = res["hits"]["hits"][0]["_source"]["authorship"]
                                if "validated" in res["hits"]["hits"][0]["_source"]:
                                    doc["validated"] = res["hits"]["hits"][0]["_source"]["validated"]
                                    if doc["validated"] and (
                                        doc["authorship"] == "firstAuthor"
                                        or doc["authorship"] == "lastAuthor"
                                        or doc["authorship"] == "correspondingAuthor"
                                    ):
                                        for cle, val in searcher.items():
                                            doc[cle] = val
                                    else:
                                        for cle, val in searcher.items():
                                            if cle in doc.keys():
                                                doc.pop(cle)

                                    if force_doc_validated:  # çà va pas RAZ si le cherche invalide ?
                                        # On devrait enlever non ?
                                        doc["validated"] = True

                                    if (
                                        res["hits"]["hits"][0]["_source"]["modifiedDate_tdate"]
                                        != doc["modifiedDate_tdate"]
                                    ):
                                        doc["records"].append(
                                            {
                                                "beforeModifiedDate_tdate": doc["modifiedDate_tdate"],
                                                "MDS": res["hits"]["hits"][0]["_source"]["MDS"],
                                            }
                                        )

                            else:
                                doc["validated"] = True

            else:
                doc_progress_recorder.set_progress(numCh+1, count, " pas de docs : " + searcher["halId_s"] )
                #print("pas de docs 4 : " + searcher["halId_s"])
            if isinstance(docs, list):
                if len(docs) > 0:
                    for indi in range(int(len(docs) // 50) + 1):
                        boutdeDoc = docs[indi * 50 : (indi * 50) + 50]
                        helpers.bulk(
                            es,
                            boutdeDoc,
                            index=searcher["structSirene"]
                            + "-"
                            + searcher["labHalId"]
                            + "-researchers-"
                            + searcher["ldapId"]
                            + "-documents"
                            # -researchers" + searcher["ldapId"] + "-documents
                        )
                        # time.sleep(1)
                    doc_progress_recorder.set_progress(
                            numCh +1, count,
                            str (len(docs)) + " documents indexés " + searcher["halId_s"]
                        )

    # if len(researchers_list) > 0:
    #     if isinstance(docs, list):
    #         doc_progress_recorder.set_progress(
    #             sommeDocs, sommeDocs, " documents traités et indexés" + str(searcher)
    #         )
    #
    #     else:
    #         pass
    #         # doc_progress_recorder.set_progress
    #         # (0, sommeDocs, " documents traités " + searcher['halId_s'])
    # else:
    #     # doc_progress_recorder.set_progress(sommeDocs, sommeDocs, " documents traités")
    #     print(f"\u00A0 \u21D2 researchers_list content = {researchers_list}")
    #     print(
    #         "\u00A0 \u21D2 ",
    #         count,
    #         " researchers found in ES, checking es_researchers list",
    #     )
    doc_progress_recorder.set_progress(
        count, count,
        str(sommeDocs) + " documents indexés pour " + str(count) + " chercheurs au total "
    )
    return "fini !"


def init_labo():
    """
    Initialise les données de l'index
    """
    # initialisation liste labos supposée plus fiables que données issues Ldap.
    labos = []
    dico_acronym = dict()

    # init es_laboratories
    count = es.count(index="*-laboratories", body=scope_param, request_timeout=50)["count"]
    if count > 0:
        print(count, " laboratories to init found in ES, processing es to init_labo")
        res = es.search(index="*-laboratories", body=scope_param, size=count, request_timeout=50)
        es_laboratories = res["hits"]["hits"]
        for lab in es_laboratories:
            lab = lab["_source"]
            lab["halStructId"] = lab["halStructId"].strip()
            if " " in lab["halStructId"]:
                connait_lab = "non-labo"
            else:
                connait_lab = lab["halStructId"]
                labos.append(connait_lab)

            if lab["acronym"] not in dico_acronym.values():
                dico_acronym[lab["halStructId"]] = lab["acronym"]

    if djangodb_open:
        djangolab = Laboratory.objects.all().values()
        [lab.pop("id") for lab in djangolab]
        for lab in djangolab:
            lab["halStructId"] = lab["halStructId"].strip()
            if " " in lab["halStructId"]:
                connait_lab = "non-labo"
            else:
                connait_lab = lab["halStructId"]
                labos.append(connait_lab)

            if lab["acronym"] not in dico_acronym.values():
                dico_acronym[lab["halStructId"]] = lab["acronym"]

    return labos, dico_acronym


def collect_data(laboratories=False, researcher=False, django_enabler=None):
    """
    Collecte les données d'HAL et les indexe dans ElasticSearch
    """
    global djangodb_open
    tache1 = tache2 = None
    djangodb_open = django_enabler
    structIdlist = get_structid_list()
    taches = []
    if laboratories:
        print("collecting laboratories data")
        tache1 = collect_laboratories_data.delay()
        taches .append(tache1)
    else:
        pass
    if researcher:
        #print("collecting researchers data")
        for struct in structIdlist:  # c'est bizarre une tache écrasée...
            tache2 = collect_researchers_data.delay(struct)
            taches.append(tache2)
    else:
        print("researcher is disabled, skipping to next process")

    print(time.strftime("%H:%M:%S", time.localtime()), end=" : ")
    print("Index completion finished")
    return taches
