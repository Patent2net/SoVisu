from __future__ import absolute_import, unicode_literals
import datetime
import csv
import time
from elasticsearch import helpers
# Custom libs
from sovisuhal.libs import esActions
from elasticHal.libs import hal, utils, archivesOuvertes, location_docs, doi_enrichissement ,keyword_enrichissement

# Celery
from celery import shared_task
# Celery-progress
from celery_progress.backend import ProgressRecorder

"""
django_init allow to run the script by using the Database integrated in django(SQLite) without passing by SoVisu.
Turn django_init value at "True" only if you intend to use the script as standalone and want to use the Database by turning djangodb_open value at "True".
Default Value: "django_init = False"
"""
django_init = None
if __name__ == '__main__':
    if django_init:
        print("init django DB access (standalone mode)")
        import os
        import django
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sovisuhal.settings")
        django.setup()  # allow to use the elastichal.models under independantly from Django

        from elasticHal.models import Laboratory, Researcher
else:
    from elasticHal.models import Laboratory, Researcher

# Global variables
structIdlist = None

check_existing_docs = True  # if True, check all the existing data in ES index to compare with those gathered to keep part of totality of data persistence

force_doc_validated = False  # if True, overwrite the doc['validated'] status to True for all the docs existing in ES (work only if Check_existing_docs = True)
force_doc_authorship = False  # if True, overwrite the doc["authorship"] status for all the docs existing in ES (work only if Check_existing_docs = True)

csv_open = None  # If csv_open = True script will use .csv stocked in elasticHal > data to generate index for ES. Default Value is True when used as a script and False when called by SoVisu.(check the code at the bottom of the file)
djangodb_open = None  # If djangodb_open = True script will use django Db to generate index for ES. Default Value is False vhen used as a script and True when called by SoVisu. (check the code at the bottom of the file)

harvet_history = []

# Connect to DB
es = esActions.es_connector()
# get structId for already existing structures in ES
scope_param = esActions.scope_all()


def get_structid_list():
    global structIdlist
    structIdlist = []
    res = es.search(index="*-structures", body=scope_param, filter_path=["hits.hits._source.structSirene"], request_timeout=50)
    print(res)
    structIdlist = [hit['_source']['structSirene'] for hit in res['hits']['hits']]
    print("\u00A0 \u21D2 ", structIdlist)
    return structIdlist

@shared_task(bind=True)
def collect_laboratories_data2(self, labo):

    # Init laboratories
    laboratories_list = []
    #progress_recorder = ProgressRecorder(self)
    doc_progress_recorder = ProgressRecorder(self)
    # init es_laboratories
    count = es.count(index="*-laboratories", body=scope_param, request_timeout=50)['count']
    #progress_recorder.set_progress(0, count, " labo traités ")
    if count > 0:
        # grosse feint, on ne récupère que le labo coché
        #print("\u00A0 \u21D2", count, "laboratories found in ES, checking es_laboratories list")
        res = es.search(index="*-laboratories", body=scope_param, size=count, request_timeout=50)
        es_laboratories = res['hits']['hits']
        for lab in es_laboratories:
            if labo == lab['_source']['halStructId']:
                laboratories_list.append(lab['_source'])

    if csv_open:
        with open('data/laboratories.csv', encoding='utf-8') as csv_file:
            csv_reader = list(csv.DictReader(csv_file, delimiter=';'))
            if laboratories_list:
                print("\u00A0 \u21D2 checking laboratories.csv list: ")

                for lab in csv_reader:
                    if any(dictlist['halStructId'] == lab['halStructId'] for dictlist in laboratories_list):
                        print(f'\u00A0 \u21D2 {lab["acronym"]} (struct: {lab["structSirene"]}) is already in laboratories_list')
                    else:
                        print(f'\u00A0 \u21D2 adding {lab["acronym"]} (struct: {lab["structSirene"]}) to laboratories_list')
                        laboratories_list.append(lab)
            else:
                print("\u00A0 \u21D2 laboratories_list is empty, adding csv content to values")
                laboratories_list = csv_reader

    if djangodb_open:
        djangolab = Laboratory.objects.all().values()
        [lab.pop('id') for lab in djangolab]
        if laboratories_list:
            print("\u00A0 \u21D2 checking DjangoDb laboratory list:")
            for lab in djangolab:
                if any(dictlist['halStructId'] == lab['halStructId'] for dictlist in laboratories_list):
                    print(f'\u00A0 \u21D2 {lab["acronym"]} (struct: {lab["structSirene"]}) is already in laboratories_list')
                else:
                    print(f'\u00A0 \u21D2 adding {lab["acronym"]} (struct: {lab["structSirene"]}) to laboratories_list')
                    laboratories_list.append(lab)
        else:
            print("\u00A0 \u21D2 laboratories_list is empty, adding DjangoDb content to values")
            laboratories_list = djangolab

    # print(f'laboratories_list values = {laboratories_list}')
    # Process laboratories
    nblab = 0
    for lab in laboratories_list:
        print(f"\u00A0 \u21D2 Processing : {lab['acronym']}")
        #progress_recorder.set_progress( nblab, count, lab['acronym'] + " labo en cours")
        nblab +=1
        # Collect publications
        if len(lab['halStructId']) > 0:
            docs = hal.find_publications(lab['halStructId'], 'labStructId_i')

            # docs = doi_enrichissement.docs_enrichissement_doi(docs)
            # docs = keyword_enrichissement.keyword_from_teeft(docs)
            # docs = keyword_enrichissement.return_entities(docs)

            # Insert documents collection
            if len(docs)>1:
                for num, doc in enumerate(docs):
                    doc_progress_recorder.set_progress(num, len(docs), "Collection "+ lab['acronym'] + " en cours")
                    print(f"- sub processing : {str(doc['docid'])}")
                    # Enrichssements des documents récoltés
                    doc ["country_colaboration"] = location_docs.generate_countrys_fields(doc)
                    lstResum = [cle for cle in doc.keys() if "abstract" in cle]
                    for cle in lstResum:
                        if isinstance(doc[cle], list):
                            doc [cle] =  ' ' .join( doc [cle] )
                        else:
                            pass
                    doc["_id"] = doc['docid']
                    doc["validated"] = True
                    doc["harvested_from"] = "lab"
                    doc["harvested_from_ids"] = []

                    doc["harvested_from_ids"].append(lab['halStructId'])
                    doc["harvested_from_label"] = []
                    doc["harvested_from_label"].append(lab['acronym'])
                    if "Created" not in doc:
                        doc['Created'] = datetime.datetime.now().isoformat()

                    doc["authorship"] = []

                    authid_s_filled = []
                    if "authId_i" in doc:
                        for auth in doc["authId_i"]:
                            try:
                                aurehal = archivesOuvertes.get_halid_s(auth)
                                authid_s_filled.append(aurehal)
                            except:
                                authid_s_filled.append("")

                    authors_count = len(authid_s_filled)
                    i = 0
                    for auth in authid_s_filled:
                        i += 1
                        if i == 1 and auth != "":
                            doc["authorship"].append({"authorship": "firstAuthor", "authFullName_s": auth})
                        elif i == authors_count and auth != "":
                            doc["authorship"].append({"authorship": "lastAuthor", "authFullName_s": auth})

                    harvet_history.append({'docid': doc['docid'], 'from': lab['halStructId']})

                    for h in harvet_history:
                        if h['docid'] == doc['docid']:
                            doc["harvested_from_ids"].append(h['from'])

                    doc["MDS"] = utils.calculate_mds(doc)
                    doc["records"] = []

                    try:
                        should_be_open = utils.should_be_open(doc)
                        if should_be_open == 1:
                            doc["should_be_open"] = True
                        if should_be_open == -1:
                            doc["should_be_open"] = False

                        if should_be_open == 1 or should_be_open == 2:
                            doc['isOaExtra'] = True
                        elif should_be_open == -1:
                            doc['isOaExtra'] = False
                    except:
                        print('publicationDate_tdate error ?')

                    if check_existing_docs:

                        doc_param = esActions.scope_p("_id", doc["_id"])

                        if not es.indices.exists(
                                index=lab['structSirene'] + "-" + lab["halStructId"] + "-laboratories-documents"):
                            es.indices.create(
                                index=lab['structSirene'] + "-" + lab["halStructId"] + "-laboratories-documents")
                        res = es.search(index=lab["structSirene"] + "-" + lab["halStructId"] + "-laboratories-documents",
                                        body=doc_param, request_timeout=50)

                        if len(res['hits']['hits']) > 0:
                            if "authorship" in res['hits']['hits'][0]['_source'] and not force_doc_authorship:
                                doc["authorship"] = res['hits']['hits'][0]['_source']['authorship']
                            if "validated" in res['hits']['hits'][0]['_source']:
                                doc['validated'] = res['hits']['hits'][0]['_source']['validated']
                            if force_doc_validated:
                                doc['validated'] = True

                            if res['hits']['hits'][0]['_source']['modifiedDate_tdate'] != doc['modifiedDate_tdate']:
                                doc["records"].append({'beforeModifiedDate_tdate': doc['modifiedDate_tdate'],
                                                       'MDS': res['hits']['hits'][0]['_source']['MDS']})
                        else:
                            doc["validated"] = True
            time.sleep(1)

            res = helpers.bulk(
                es,
                docs,
                index=lab["structSirene"] + "-" + lab["halStructId"] + "-laboratories-documents",
                request_timeout = 50
            )
            doc_progress_recorder.set_progress(len(docs), len(docs), lab['acronym']+ " " + str(len(docs)) + " documents")
        #progress_recorder.set_progress(nblab, count, lab['acronym'] + " labo traité")

    return "finished"

@shared_task(bind=True)
def collect_researchers_data(self, struct):
    # initialisation liste labos supposée plus fiables que données issues Ldap.
    progress_recorder= ProgressRecorder(self)
    doc_progress_recorder= ProgressRecorder(self)
    labos, dico_acronym = init_labo()
    print(f"\u00A0 \u21D2 labos values ={labos}")
    print(f"\u00A0 \u21D2 dicoAcronym values ={dico_acronym}")
    # Init researchers
    researchers_list = []

    count = es.count(index=struct + "*-researchers", body=scope_param, request_timeout=50)['count']
    if count > 0:
        print("\u00A0 \u21D2 ", count, " researchers found in ES, checking es_researchers list")
        res = es.search(index=struct + "*-researchers", body=scope_param, size=count, request_timeout=50)
        es_researchers = res['hits']['hits']
        i=0
        for searcher in es_researchers:

            researchers_list.append(searcher['_source'])

    if csv_open:
        with open('data/researchers.csv', encoding='utf-8') as csv_file:
            csv_reader = list(csv.DictReader(csv_file, delimiter=','))
            csv_reader = [searcher for searcher in csv_reader if searcher['halId_s'] != '']  # Only keep researchers with known 'halId_s'
            if researchers_list:
                print("\u00A0 \u21D2 checking researchers.csv list: ")
                for searcher in csv_reader:
                    if any(dictlist['halId_s'] == searcher['halId_s'] for dictlist in researchers_list):
                        print(f'\u00A0 \u21D2 {searcher["name"]} (ldapId: {searcher["ldapId"]}) is already in researchers_list')
                    else:
                        print(f'\u00A0 \u21D2 adding {searcher["name"]} (ldapId: {searcher["ldapId"]}) to researchers_list')
                        researchers_list.append(searcher)
            else:
                print("\u00A0 \u21D2 researchers_list is empty, adding csv content to values")
                researchers_list = csv_reader

    if djangodb_open:
        django_researchers = Researcher.objects.all().values()
        django_researchers = [researcher for researcher in django_researchers if researcher['halId_s'] != '' and researcher.pop('id')]  # Only keep researchers with known 'halId_s' and remove the 'id' value created by Django_DB
        if researchers_list:
            print("checking DjangoDb laboratory list:")
            for searcher in django_researchers:
                if any(dictlist['halId_s'] == searcher['halId_s'] for dictlist in researchers_list):
                    print(f'\u00A0 \u21D2 {searcher["name"]} (ldapId: {searcher["ldapId"]}) is already in researchers_list')
                else:
                    print(f'\u00A0 \u21D2 adding {searcher["name"]} (ldapId: {searcher["ldapId"]}) to researchers_list')
                    researchers_list.append(searcher)
        else:
            print("\u00A0 \u21D2 researchers_list is empty, adding DjangoDb content to values")
            researchers_list = django_researchers

    print(f'\u00A0 \u21D2 researchers_list content = {researchers_list}')
    # Process researchers
    j = 0
    for searcher in researchers_list:
        progress_recorder.set_progress(j, count, " chercheurs traités ")

        if searcher["structSirene"] == struct:  # seulement les chercheurs de la structure
            #print(f"\u00A0 \u21D2 Processing : {searcher['halId_s']}")
            if searcher["labHalId"] not in labos:
                searcher["labHalId"] = "non-labo"
            # Collect publications
            j += 1
            k = 0
            docs = hal.find_publications(searcher['halId_s'], 'authIdHal_s')
            # Enrichssements des documents récoltés

            # Insert documents collection
            if len(docs)>1:
                for num, doc in enumerate(docs):
                    k += 1
                    doc_progress_recorder.set_progress(num, len(docs), " document traités " + searcher['halId_s'])
                    doc["country_colaboration"] = location_docs.generate_countrys_fields(doc)
                    doc = doi_enrichissement.docs_enrichissement_doi(doc)
                    if "fr_abstract_s" in doc.keys():
                        if isinstance(doc["fr_abstract_s"], list):
                            doc["fr_abstract_s"] = "/n" .join(doc["fr_abstract_s"])
                        if len(doc["fr_abstract_s"]) > 100:
                            doc["fr_entites"]= keyword_enrichissement.return_entities(doc["fr_abstract_s"], 'fr')
                            doc["fr_teeft_keywords"]= keyword_enrichissement.keyword_from_teeft(doc["fr_abstract_s"], 'fr')
                    if "en_abstract_s" in doc.keys():
                        if isinstance(doc["en_abstract_s"], list):
                            doc["en_abstract_s"] = "/n" .join(doc["en_abstract_s"])
                        if len(doc["en_abstract_s"]) > 100:
                            doc["en_entites"]= keyword_enrichissement.return_entities(doc["en_abstract_s"], 'en')
                            doc["en_teeft_keywords"] = keyword_enrichissement.keyword_from_teeft(doc["en_abstract_s"], 'en')
                    doc["_id"] = doc['docid']
                    doc["validated"] = True

                    doc["harvested_from"] = "researcher"

                    doc["harvested_from_ids"] = []
                    doc["harvested_from_label"] = []
                    try:
                        doc["harvested_from_label"].append(dico_acronym[searcher["labHalId"]])
                    except:
                        doc["harvested_from_label"].append("non-labo")

                    doc["authorship"] = []

                    if "authIdHal_s" in doc:
                        authors_count = len(doc["authIdHal_s"])
                        i = 0
                        for auth in doc["authIdHal_s"]:
                            i += 1
                            if i == 1:
                                doc["authorship"].append({"authorship": "firstAuthor", "halId_s": auth})
                            elif i == authors_count:
                                doc["authorship"].append({"authorship": "lastAuthor", "halId_s": auth})
                    if "Created" not in doc:
                        doc['Created'] = datetime.datetime.now().isoformat()

                    doc["harvested_from_ids"].append(searcher['halId_s'])
                    # historique d'appartenance du docId
                    # pour attribuer les bons docs aux chercheurs
                    harvet_history.append({'docid': doc['docid'], 'from': searcher['halId_s']})

                    for h in harvet_history:
                        if h['docid'] == doc['docid']:
                            if h['from'] not in doc["harvested_from_ids"]:
                                doc["harvested_from_ids"].append(h['from'])

                    doc["records"] = []
                    doc["MDS"] = utils.calculate_mds(doc)

                    try:
                        should_be_open = utils.should_be_open(doc)
                        if should_be_open == 1:
                            doc["should_be_open"] = True
                        if should_be_open == -1:
                            doc["should_be_open"] = False

                        if should_be_open == 1 or should_be_open == 2:
                            doc['isOaExtra'] = True
                        elif should_be_open == -1:
                            doc['isOaExtra'] = False
                    except:
                        print('publicationDate_tdate error ?')

                    if check_existing_docs:
                        doc_param = esActions.scope_p("_id", doc["_id"])

                        if not es.indices.exists(index=searcher["structSirene"] + "-" + searcher["labHalId"] + "-researchers-" + searcher["ldapId"] + "-documents"):  # -researchers" + searcher["ldapId"] + "-documents
                            print(f'exception {searcher["labHalId"]}, {searcher["ldapId"]}')
                            break
                        res = es.search(index=searcher["structSirene"] + "-" + searcher["labHalId"] + "-researchers-" + searcher[
                            "ldapId"] + "-documents", body=doc_param, request_timeout=50)  # -researchers" + searcher["ldapId"] + "-documents

                        if len(res['hits']['hits']) > 0:
                            if "authorship" in res['hits']['hits'][0]['_source'] and not force_doc_authorship:
                                doc["authorship"] = res['hits']['hits'][0]['_source']['authorship']
                            if "validated" in res['hits']['hits'][0]['_source']:
                                doc['validated'] = res['hits']['hits'][0]['_source']['validated']
                            if force_doc_validated:
                                doc['validated'] = True

                            if res['hits']['hits'][0]['_source']['modifiedDate_tdate'] != doc['modifiedDate_tdate']:
                                doc["records"].append({'beforeModifiedDate_tdate': doc['modifiedDate_tdate'],
                                                       'MDS': res['hits']['hits'][0]['_source']['MDS']})

                        else:
                            doc["validated"] = True

                time.sleep(1)
            else:
                print ("pas de docs", searcher['halId_s'])
            res = helpers.bulk(
                es,
                docs,
                request_timeout=50,
                index=searcher["structSirene"] + "-" + searcher["labHalId"] + "-researchers-" + searcher["ldapId"] + "-documents",
                # -researchers" + searcher["ldapId"] + "-documents
            )
            doc_progress_recorder.set_progress(k, len(docs), " document traités "+ searcher["labHalId"])
        else:
            print(f"\u00A0 \u21D2 chercheur hors structure, {searcher['ldapId']}, structure : {searcher['structSirene']}")

    doc_progress_recorder.set_progress(len(docs), len(docs), " document traités " + searcher['ldapId'])
    progress_recorder.set_progress(count, count, " chercheurs traités "+searcher['ldapId'])
    return "finished"


@shared_task(bind=True)
def collect_laboratories_data(self):
    print("uuuuuuuu")
    # Init laboratories
    laboratories_list = []
    progress_recorder = ProgressRecorder(self)
    doc_progress_recorder = ProgressRecorder(self)
    # init es_laboratories
    count = es.count(index="*-laboratories", body=scope_param, request_timeout=50)['count']
    progress_recorder.set_progress(0, count, " labo traités ")
    if count > 0:
        print("\u00A0 \u21D2", count, "laboratories found in ES, checking es_laboratories list")
        res = es.search(index="*-laboratories", body=scope_param, size=count, request_timeout=50)
        es_laboratories = res['hits']['hits']
        for lab in es_laboratories:
            laboratories_list.append(lab['_source'])

    if csv_open:
        with open('data/laboratories.csv', encoding='utf-8') as csv_file:
            csv_reader = list(csv.DictReader(csv_file, delimiter=';'))
            if laboratories_list:
                print("\u00A0 \u21D2 checking laboratories.csv list: ")

                for lab in csv_reader:
                    if any(dictlist['halStructId'] == lab['halStructId'] for dictlist in laboratories_list):
                        print(f'\u00A0 \u21D2 {lab["acronym"]} (struct: {lab["structSirene"]}) is already in laboratories_list')
                    else:
                        print(f'\u00A0 \u21D2 adding {lab["acronym"]} (struct: {lab["structSirene"]}) to laboratories_list')
                        laboratories_list.append(lab)
            else:
                print("\u00A0 \u21D2 laboratories_list is empty, adding csv content to values")
                laboratories_list = csv_reader

    if djangodb_open:
        djangolab = Laboratory.objects.all().values()
        [lab.pop('id') for lab in djangolab]
        if laboratories_list:
            print("\u00A0 \u21D2 checking DjangoDb laboratory list:")
            for lab in djangolab:
                if any(dictlist['halStructId'] == lab['halStructId'] for dictlist in laboratories_list):
                    print(f'\u00A0 \u21D2 {lab["acronym"]} (struct: {lab["structSirene"]}) is already in laboratories_list')
                else:
                    print(f'\u00A0 \u21D2 adding {lab["acronym"]} (struct: {lab["structSirene"]}) to laboratories_list')
                    laboratories_list.append(lab)
        else:
            print("\u00A0 \u21D2 laboratories_list is empty, adding DjangoDb content to values")
            laboratories_list = djangolab

    # print(f'laboratories_list values = {laboratories_list}')
    # Process laboratories
    nblab = 0
    for lab in laboratories_list:
        print(f"\u00A0 \u21D2 Processing : {lab['acronym']}")
        progress_recorder.set_progress( nblab, count, lab['acronym'] + " labo en cours")
        nblab +=1
        # Collect publications
        if len(lab['halStructId']) > 0:
            docs = hal.find_publications(lab['halStructId'], 'labStructId_i')

            # docs = doi_enrichissement.docs_enrichissement_doi(docs)
            # docs = keyword_enrichissement.keyword_from_teeft(docs)
            # docs = keyword_enrichissement.return_entities(docs)

            # Insert documents collection
            if len(docs)>1:
                for num, doc in enumerate(docs):
                    doc_progress_recorder.set_progress(num, len(docs), "Collection "+ lab['acronym'] + " en cours")
                    print(f"- sub processing : {str(doc['docid'])}")
                    # Enrichssements des documents récoltés
                    doc ["country_colaboration"] = location_docs.generate_countrys_fields(doc)
                    lstResum = [cle for cle in doc.keys() if "abstract" in cle]
                    for cle in lstResum:
                        if isinstance(doc[cle], list):
                            doc [cle] =  ' ' .join( doc [cle] )
                        else:
                            pass
                    doc["_id"] = doc['docid']
                    doc["validated"] = True
                    doc["harvested_from"] = "lab"
                    doc["harvested_from_ids"] = []

                    doc["harvested_from_ids"].append(lab['halStructId'])
                    doc["harvested_from_label"] = []
                    doc["harvested_from_label"].append(lab['acronym'])
                    if "Created" not in doc:
                        doc['Created'] = datetime.datetime.now().isoformat()

                    doc["authorship"] = []

                    authid_s_filled = []
                    if "authId_i" in doc:
                        for auth in doc["authId_i"]:
                            try:
                                aurehal = archivesOuvertes.get_halid_s(auth)
                                authid_s_filled.append(aurehal)
                            except:
                                authid_s_filled.append("")

                    authors_count = len(authid_s_filled)
                    i = 0
                    for auth in authid_s_filled:
                        i += 1
                        if i == 1 and auth != "":
                            doc["authorship"].append({"authorship": "firstAuthor", "authFullName_s": auth})
                        elif i == authors_count and auth != "":
                            doc["authorship"].append({"authorship": "lastAuthor", "authFullName_s": auth})

                    harvet_history.append({'docid': doc['docid'], 'from': lab['halStructId']})

                    for h in harvet_history:
                        if h['docid'] == doc['docid']:
                            doc["harvested_from_ids"].append(h['from'])

                    doc["MDS"] = utils.calculate_mds(doc)
                    doc["records"] = []

                    try:
                        should_be_open = utils.should_be_open(doc)
                        if should_be_open == 1:
                            doc["should_be_open"] = True
                        if should_be_open == -1:
                            doc["should_be_open"] = False

                        if should_be_open == 1 or should_be_open == 2:
                            doc['isOaExtra'] = True
                        elif should_be_open == -1:
                            doc['isOaExtra'] = False
                    except:
                        print('publicationDate_tdate error ?')

                    if check_existing_docs:

                        doc_param = esActions.scope_p("_id", doc["_id"])

                        if not es.indices.exists(
                                index=lab['structSirene'] + "-" + lab["halStructId"] + "-laboratories-documents"):
                            es.indices.create(
                                index=lab['structSirene'] + "-" + lab["halStructId"] + "-laboratories-documents")
                        res = es.search(index=lab["structSirene"] + "-" + lab["halStructId"] + "-laboratories-documents",
                                        body=doc_param, request_timeout=50)

                        if len(res['hits']['hits']) > 0:
                            if "authorship" in res['hits']['hits'][0]['_source'] and not force_doc_authorship:
                                doc["authorship"] = res['hits']['hits'][0]['_source']['authorship']
                            if "validated" in res['hits']['hits'][0]['_source']:
                                doc['validated'] = res['hits']['hits'][0]['_source']['validated']
                            if force_doc_validated:
                                doc['validated'] = True

                            if res['hits']['hits'][0]['_source']['modifiedDate_tdate'] != doc['modifiedDate_tdate']:
                                doc["records"].append({'beforeModifiedDate_tdate': doc['modifiedDate_tdate'],
                                                       'MDS': res['hits']['hits'][0]['_source']['MDS']})
                        else:
                            doc["validated"] = True
            time.sleep(1)

            res = helpers.bulk(
                es,
                docs,
                index=lab["structSirene"] + "-" + lab["halStructId"] + "-laboratories-documents",
                request_timeout = 50
            )
            doc_progress_recorder.set_progress(len(docs), len(docs), lab['acronym']+ " " + str(len(docs)) + " documents")
        progress_recorder.set_progress(nblab, count, lab['acronym'] + " labo traité")

    return "finished"
@shared_task(bind=True)
def collect_researchers_data2(self, struct, idx):
    # initialisation liste labos supposée plus fiables que données issues Ldap.
    #progress_recorder= ProgressRecorder(self)
    doc_progress_recorder= ProgressRecorder(self)

    # Init researchers
    researchers_list = []
    labos, dico_acronym = init_labo()
    idxCher = idx .replace("laboratories", "researchers*")
    count = es.count(index=idxCher, body=scope_param, request_timeout=50)['count']
    if count > 0:
        print("\u00A0 \u21D2 ", count, " researchers found in ES, checking es_researchers list")
        res = es.search(index=idxCher, body=scope_param, size=count, request_timeout=50)

        es_researchers = res['hits']['hits']
        i=0
        for searcher in es_researchers:

            researchers_list.append(searcher['_source'])

    print(f'\u00A0 \u21D2 researchers_list content = {researchers_list}')
    # Process researchers
    sommeDocs = 0
    for searcher in researchers_list:
        #progress_recorder.set_progress(j, count, " chercheurs traités ")
        print ("hooo", searcher .keys(), researchers_list, idxCher)
        #if searcher["structSirene"] == struct:  # seulement les chercheurs de la structure
            #print(f"\u00A0 \u21D2 Processing : {searcher['halId_s']}")
            # Collect publications

        k = 0
        docs = hal.find_publications(searcher['halId_s'], 'authIdHal_s')
            # Enrichssements des documents récoltés
        sommeDocs += len(docs)
        doc_progress_recorder.set_progress(k, len(docs), " document traités " + searcher["labHalId"])
            # Insert documents collection
        if len(docs)>1:
                for num, doc in enumerate(docs):
                    k += 1
                    doc_progress_recorder.set_progress(num, len(docs), " document traités " + searcher['halId_s'])
                    doc["country_colaboration"] = location_docs.generate_countrys_fields(doc)
                    doc = doi_enrichissement.docs_enrichissement_doi(doc)
                    if "fr_abstract_s" in doc.keys():
                        if isinstance(doc["fr_abstract_s"], list):
                            doc["fr_abstract_s"] = "/n" .join(doc["fr_abstract_s"])
                        if len(doc["fr_abstract_s"]) > 100:
                            doc["fr_entites"]= keyword_enrichissement.return_entities(doc["fr_abstract_s"], 'fr')
                            doc["fr_teeft_keywords"]= keyword_enrichissement.keyword_from_teeft(doc["fr_abstract_s"], 'fr')
                    if "en_abstract_s" in doc.keys():
                        if isinstance(doc["en_abstract_s"], list):
                            doc["en_abstract_s"] = "/n" .join(doc["en_abstract_s"])
                        if len(doc["en_abstract_s"]) > 100:
                            doc["en_entites"]= keyword_enrichissement.return_entities(doc["en_abstract_s"], 'en')
                            doc["en_teeft_keywords"] = keyword_enrichissement.keyword_from_teeft(doc["en_abstract_s"], 'en')
                    doc["_id"] = doc['docid']
                    doc["validated"] = True

                    doc["harvested_from"] = "researcher"

                    doc["harvested_from_ids"] = []
                    doc["harvested_from_label"] = []
                    try:
                        doc["harvested_from_label"].append(dico_acronym[searcher["labHalId"]])
                    except:
                        doc["harvested_from_label"].append("non-labo")

                    doc["authorship"] = []

                    if "authIdHal_s" in doc:
                        authors_count = len(doc["authIdHal_s"])
                        i = 0
                        for auth in doc["authIdHal_s"]:
                            i += 1
                            if i == 1:
                                doc["authorship"].append({"authorship": "firstAuthor", "halId_s": auth})
                            elif i == authors_count:
                                doc["authorship"].append({"authorship": "lastAuthor", "halId_s": auth})
                    if "Created" not in doc:
                        doc['Created'] = datetime.datetime.now().isoformat()

                    doc["harvested_from_ids"].append(searcher['halId_s'])
                    # historique d'appartenance du docId
                    # pour attribuer les bons docs aux chercheurs
                    harvet_history.append({'docid': doc['docid'], 'from': searcher['halId_s']})

                    for h in harvet_history:
                        if h['docid'] == doc['docid']:
                            if h['from'] not in doc["harvested_from_ids"]:
                                doc["harvested_from_ids"].append(h['from'])

                    doc["records"] = []
                    doc["MDS"] = utils.calculate_mds(doc)

                    try:
                        should_be_open = utils.should_be_open(doc)
                        if should_be_open == 1:
                            doc["should_be_open"] = True
                        if should_be_open == -1:
                            doc["should_be_open"] = False

                        if should_be_open == 1 or should_be_open == 2:
                            doc['isOaExtra'] = True
                        elif should_be_open == -1:
                            doc['isOaExtra'] = False
                    except:
                        print('publicationDate_tdate error ?')

                    if check_existing_docs:
                        doc_param = esActions.scope_p("_id", doc["_id"])

                        if not es.indices.exists(index=searcher["structSirene"] + "-" + searcher["labHalId"] + "-researchers-" + searcher["ldapId"] + "-documents"):  # -researchers" + searcher["ldapId"] + "-documents
                            print(f'exception {searcher["labHalId"]}, {searcher["ldapId"]}')
                            break
                        res = es.search(index=searcher["structSirene"] + "-" + searcher["labHalId"] + "-researchers-" + searcher[
                            "ldapId"] + "-documents", body=doc_param, request_timeout=50)  # -researchers" + searcher["ldapId"] + "-documents

                        if len(res['hits']['hits']) > 0:
                            if "authorship" in res['hits']['hits'][0]['_source'] and not force_doc_authorship:
                                doc["authorship"] = res['hits']['hits'][0]['_source']['authorship']
                            if "validated" in res['hits']['hits'][0]['_source']:
                                doc['validated'] = res['hits']['hits'][0]['_source']['validated']
                            if force_doc_validated:
                                doc['validated'] = True

                            if res['hits']['hits'][0]['_source']['modifiedDate_tdate'] != doc['modifiedDate_tdate']:
                                doc["records"].append({'beforeModifiedDate_tdate': doc['modifiedDate_tdate'],
                                                       'MDS': res['hits']['hits'][0]['_source']['MDS']})

                        else:
                            doc["validated"] = True

                time.sleep(1)
        else:
                print ("pas de docs", searcher['halId_s'])

        res = helpers.bulk(
                es,
                docs,
                request_timeout=50,
                index=searcher["structSirene"] + "-" + searcher["labHalId"] + "-researchers-" + searcher["ldapId"] + "-documents",
                # -researchers" + searcher["ldapId"] + "-documents
            )
        doc_progress_recorder.set_progress(len(docs)-1, sommeDocs, " document traités " + searcher['ldapId'])
        #else:
            # impossible d'être là
        #    print(f"\u00A0 \u21D2 chercheur hors structure, {searcher['ldapId']}, structure : {searcher['structSirene']}")

    doc_progress_recorder.set_progress(sommeDocs, sommeDocs, " document traités " + searcher['ldapId'])
    #progress_recorder.set_progress(count, count, " chercheurs traités "+searcher['ldapId'])
    return "fini !"

def init_labo():
    # initialisation liste labos supposée plus fiables que données issues Ldap.
    labos = []
    dico_acronym = dict()

    # init es_laboratories
    count = es.count(index="*-laboratories", body=scope_param, request_timeout=50)['count']
    if count > 0:
        print(count, " laboratories to init found in ES, processing es to init_labo")
        res = es.search(index="*-laboratories", body=scope_param, size=count, request_timeout=50)
        es_laboratories = res['hits']['hits']
        for lab in es_laboratories:
            lab = lab['_source']
            lab["halStructId"] = lab["halStructId"].strip()
            if " " in lab["halStructId"]:
                connait_lab = "non-labo"
            else:
                connait_lab = lab["halStructId"]
                labos.append(connait_lab)

            if lab['acronym'] not in dico_acronym.values():
                dico_acronym[lab['halStructId']] = lab['acronym']

    if csv_open:
        with open('data/laboratories.csv', encoding='utf-8') as csv_file:
            csv_reader = csv.DictReader(csv_file, delimiter=';')
            for lab in csv_reader:
                lab["halStructId"] = lab["halStructId"].strip()
                if " " in lab["halStructId"]:
                    connait_lab = "non-labo"
                else:
                    connait_lab = lab["halStructId"]
                    labos.append(connait_lab)

                if lab['acronym'] not in dico_acronym.values():
                    dico_acronym[lab['halStructId']] = lab['acronym']

    if djangodb_open:
        djangolab = Laboratory.objects.all().values()
        [lab.pop('id') for lab in djangolab]
        for lab in djangolab:
            lab["halStructId"] = lab["halStructId"].strip()
            if " " in lab["halStructId"]:
                connait_lab = "non-labo"
            else:
                connait_lab = lab["halStructId"]
                labos.append(connait_lab)

            if lab['acronym'] not in dico_acronym.values():
                dico_acronym[lab['halStructId']] = lab['acronym']

    return labos, dico_acronym


def collect_data(laboratories=False, researcher=False, csv_enabler=True, django_enabler=None):
    global csv_open, djangodb_open

    csv_open = csv_enabler
    djangodb_open = django_enabler
    print("\u2022", time.strftime("%H:%M:%S", time.localtime()), end=' : ')
    print('Begin index completion')

    print("\u2022", time.strftime("%H:%M:%S", time.localtime()), end=' : ')
    print('processing get_structid_list')
    structIdlist = get_structid_list()

    print("\u2022", time.strftime("%H:%M:%S", time.localtime()), end=' : ')
    if laboratories:
        print('collecting laboratories data')
        tache1 = collect_laboratories_data.delay()
    else:
        tache1 = None
        print('laboratories is disabled, skipping to next process')

    print("\u2022", time.strftime("%H:%M:%S", time.localtime()), end=' : ')
    if researcher:
        print('collecting researchers data')
        for struct in structIdlist:
            tache2 = collect_researchers_data.delay(struct)
    else:
        tache2 = None
        print('researcher is disabled, skipping to next process')

    print(time.strftime("%H:%M:%S", time.localtime()), end=' : ')
    print('Index completion finished')
    return tache1, tache2

if __name__ == '__main__':
    collect_data(laboratories='on', researcher='on')
