import datetime
import csv
import time
from elasticsearch import helpers
# Custom libs
from sovisuhal.libs import esActions
from elasticHal.libs import hal, utils, archivesOuvertes, location_docs, doi_enrichissement

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
res = es.search(index="*-structures", body=scope_param, filter_path=["hits.hits._source.structSirene"])
structIdlist = [hit['_source']['structSirene'] for hit in res['hits']['hits']]
print(structIdlist)


def collect_laboratories_data():
    # Init laboratories
    laboratories_list = []

    # init es_laboratories
    count = es.count(index="*-laboratories", body=scope_param)['count']
    if count > 0:
        print(count, " laboratories found in ES, checking es_laboratories list")
        res = es.search(index="*-laboratories", body=scope_param, size=count)
        es_laboratories = res['hits']['hits']
        for lab in es_laboratories:
            laboratories_list.append(lab['_source'])

    if csv_open:
        with open('data/laboratories.csv', encoding='utf-8') as csv_file:
            csv_reader = list(csv.DictReader(csv_file, delimiter=';'))
            if laboratories_list:
                print("checking laboratories.csv list: ")

                for lab in csv_reader:
                    if any(dictlist['halStructId'] == lab['halStructId'] for dictlist in laboratories_list):
                        print(f'{lab["acronym"]} (struct: {lab["structSirene"]}) is already in laboratories_list')
                    else:
                        print(f'adding {lab["acronym"]} (struct: {lab["structSirene"]}) to laboratories_list')
                        laboratories_list.append(lab)
            else:
                print("laboratories_list is empty, adding csv content to values")
                laboratories_list = csv_reader

    if djangodb_open:
        djangolab = Laboratory.objects.all().values()
        djangolab = list([lab.pop('id') for lab in djangolab])
        if laboratories_list:
            print("checking DjangoDb laboratory list:")
            for lab in djangolab:
                if any(dictlist['halStructId'] == lab['halStructId'] for dictlist in laboratories_list):
                    print(f'{lab["acronym"]} (struct: {lab["structSirene"]}) is already in laboratories_list')
                else:
                    print(f'adding {lab["acronym"]} (struct: {lab["structSirene"]}) to laboratories_list')
                    laboratories_list.append(lab)
        else:
            print("laboratories_list is empty, adding DjangoDb content to values")
            laboratories_list = djangolab

    # print(f'laboratories_list values = {laboratories_list}')
    # Process laboratories
    for lab in laboratories_list:
        print(f"Processing : {lab['acronym']}")
        # Collect publications
        if len(lab['halStructId']) > 0:
            docs = hal.find_publications(lab['halStructId'], 'labStructId_i')
            # Enrichssements des documents récoltés
            docs = location_docs.generate_countrys_fields(docs)
            docs = doi_enrichissement.docs_enrichissement_doi(docs)
            # Insert documents collection
            for num, doc in enumerate(docs):
                print(f"- sub processing : {str(doc['docid'])}")
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
                                    body=doc_param)

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
            )


def collect_researchers_data():
    # initialisation liste labos supposée plus fiables que données issues Ldap.
    labos, dico_acronym = init_labo()
    print(f"labos values ={labos}")
    print(f"dicoAcronym values ={dico_acronym}")
    # Init researchers
    researchers_list = []

    count = es.count(index="*-researchers", body=scope_param)['count']
    if count > 0:
        print(count, " researchers found in ES, checking es_researchers list")
        res = es.search(index="*-researchers", body=scope_param, size=count)
        es_researchers = res['hits']['hits']
        for searcher in es_researchers:
            researchers_list.append(searcher['_source'])

    if csv_open:
        with open('data/researchers.csv', encoding='utf-8') as csv_file:
            csv_reader = list(csv.DictReader(csv_file, delimiter=','))
            csv_reader = [searcher for searcher in csv_reader if searcher['halId_s'] != '']  # Only keep researchers with known 'halId_s'
            if researchers_list:
                print("checking researchers.csv list: ")
                for searcher in csv_reader:
                    if any(dictlist['halId_s'] == searcher['halId_s'] for dictlist in researchers_list):
                        print(f'{searcher["name"]} (ldapId: {searcher["ldapId"]}) is already in researchers_list')
                    else:
                        print(f'adding {searcher["name"]} (ldapId: {searcher["ldapId"]}) to researchers_list')
                        researchers_list.append(searcher)
            else:
                print("researchers_list is empty, adding csv content to values")
                researchers_list = csv_reader

    if djangodb_open:
        django_researchers = Researcher.objects.all().values()
        django_researchers = list([researcher for researcher in django_researchers if researcher['halId_s'] != '' and researcher.pop('id')])  # Only keep researchers with known 'halId_s' and remove the 'id' value created by Django_DB
        if researchers_list:
            print("checking DjangoDb laboratory list:")
            for searcher in django_researchers:
                if any(dictlist['halId_s'] == searcher['halId_s'] for dictlist in researchers_list):
                    print(f'{searcher["name"]} (ldapId: {searcher["ldapId"]}) is already in researchers_list')
                else:
                    print(f'adding {searcher["name"]} (ldapId: {searcher["ldapId"]}) to researchers_list')
                    researchers_list.append(searcher)
        else:
            print("researchers_list is empty, adding DjangoDb content to values")
            researchers_list = django_researchers

    print(f'researchers_list content = {researchers_list}')
    # Process researchers
    for searcher in researchers_list:
        if searcher["structSirene"] in structIdlist:  # seulement les chercheurs de la structure
            print(f"Processing : {searcher['halId_s']}")
            if searcher["labHalId"] not in labos:
                searcher["labHalId"] = "non-labo"
            # Collect publications
            docs = hal.find_publications(searcher['halId_s'], 'authIdHal_s')
            # Enrichssements des documents récoltés
            docs = location_docs.generate_countrys_fields(docs)
            docs = doi_enrichissement.docs_enrichissement_doi(docs)
            # Insert documents collection
            for num, doc in enumerate(docs):
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
                        "ldapId"] + "-documents", body=doc_param)  # -researchers" + searcher["ldapId"] + "-documents

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
                index=searcher["structSirene"] + "-" + searcher["labHalId"] + "-researchers-" + searcher["ldapId"] + "-documents",
                # -researchers" + searcher["ldapId"] + "-documents
            )
        else:
            print(f"chercheur hors structure, {searcher['ldapId']}, structure : {searcher['structSirene']}")


def init_labo():
    # initialisation liste labos supposée plus fiables que données issues Ldap.
    labos = []
    dico_acronym = dict()

    # init es_laboratories
    count = es.count(index="*-laboratories", body=scope_param)['count']
    if count > 0:
        print(count, " laboratories to init found in ES, processing es to init_labo")
        res = es.search(index="*-laboratories", body=scope_param, size=count)
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
        djangolab = list([lab.pop('id') for lab in djangolab])
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


def collect_data(laboratories, researcher, csv_enabler=True, django_enabler=None):
    global csv_open, djangodb_open
    csv_open = csv_enabler
    djangodb_open = django_enabler
    print(time.strftime("%H:%M:%S", time.localtime()), end=' : ')
    print('harvesting started')

    print(time.strftime("%H:%M:%S", time.localtime()), end=' : ')
    if laboratories:
        print('collecting laboratories data')
        collect_laboratories_data()
    else:
        print('laboratories is disabled, skipping to next process')

    print(time.strftime("%H:%M:%S", time.localtime()), end=' : ')
    if researcher:
        print('collecting researchers data')
        collect_researchers_data()
    else:
        print('researcher is disabled, skipping to next process')

    print(time.strftime("%H:%M:%S", time.localtime()), end=' : ')
    print('harvesting finished')


if __name__ == '__main__':
    collect_data(laboratories=None, researcher='on')
