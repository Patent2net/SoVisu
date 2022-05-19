import csv
import time
from elasticsearch import helpers
# Custom libs
from sovisuhal.libs import esActions
from elasticHal.libs import hal, utils, unpaywall, location_docs

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
init = True  # if init = True overwrite the validated status

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
    # Process laboratories
    laboratories_list = []
    if csv_open:
        with open('data/laboratories.csv', encoding='utf-8') as csv_file:
            csv_reader = list(csv.DictReader(csv_file, delimiter=';'))
            if laboratories_list:
                print("checking laboratories.csv list: ")

                for lab in csv_reader:
                    if any(dictlist['halStructId'] == lab['halStructId'] for dictlist in laboratories_list):
                        print(f'{lab["acronym"]} is already in laboratories_list')
                    else:
                        print(f'adding {lab["acronym"]} to laboratories_list')
                        laboratories_list.append(lab)
            else:
                print("laboratories_list is empty, adding csv content to values")
                laboratories_list = csv_reader

    if djangodb_open:
        if laboratories_list:
            print("checking DjangoDb laboratory list:")
            for lab in Laboratory.objects.all().values():
                lab.pop('id')
                if any(dictlist['halStructId'] == lab['halStructId'] for dictlist in laboratories_list):
                    print(f'{lab["acronym"]} is already in laboratories_list')
                else:
                    print(f'adding {lab["acronym"]} to laboratories_list')
                    laboratories_list.append(lab)
        else:
            print("laboratories_list is empty, adding DjangoDb content to values")
            for lab in Laboratory.objects.all().values():
                lab.pop('id')
                laboratories_list.append(lab)

    print(f'laboratories_list values = {laboratories_list}')
    for row in laboratories_list:
        print(f"Processing : {row['acronym']}")
        # Collect publications
        if len(row['halStructId']) > 0:
            docs = hal.find_publications(row['halStructId'], 'labStructId_i')
            docs = location_docs.generate_countrys_fields(docs)
            # Insert documents collection
            for num, doc in enumerate(docs):
                print(f"- sub processing : {str(doc['docid'])}")
                doc["_id"] = doc['docid']
                doc["validated"] = True
                doc["harvested_from"] = "lab"
                doc["harvested_from_ids"] = []

                doc["harvested_from_ids"].append(row['halStructId'])
                doc["harvested_from_label"] = []
                doc["harvested_from_label"].append(row['acronym'])

                harvet_history.append({'docid': doc['docid'], 'from': row['halStructId']})

                for h in harvet_history:
                    if h['docid'] == doc['docid']:
                        doc["harvested_from_ids"].append(h['from'])

                if 'doiId_s' in doc:
                    tmp_unpaywall = unpaywall.get_oa(doc['doiId_s'])
                    if 'is_oa' in tmp_unpaywall: doc['is_oa'] = tmp_unpaywall['is_oa']
                    if 'oa_status' in tmp_unpaywall: doc['oa_status'] = tmp_unpaywall['oa_status']
                    if 'oa_host_type' in tmp_unpaywall: doc['oa_host_type'] = tmp_unpaywall['oa_host_type']

                doc["MDS"] = utils.calculate_mds(doc)

                doc["records"] = []

                try:
                    shouldBeOpen = utils.should_be_open(doc)
                    if shouldBeOpen == 1:
                        doc["should_be_open"] = True
                    if shouldBeOpen == -1:
                        doc["should_be_open"] = False

                    if shouldBeOpen == 1 or shouldBeOpen == 2:
                        doc['isOaExtra'] = True
                    elif shouldBeOpen == -1:
                        doc['isOaExtra'] = False
                except:
                    print('publicationDate_tdate error ?')

                if not init:

                    doc_param = esActions.scope_p("_id", doc["_id"])

                    if not es.indices.exists(
                            index=row['structSirene'] + "-" + row["halStructId"] + "-laboratories-documents"):
                        es.indices.create(
                            index=row['structSirene'] + "-" + row["halStructId"] + "-laboratories-documents")
                    res = es.search(
                        index=row["structSirene"] + "-" + row["halStructId"] + "-laboratories-documents",
                        body=doc_param)

                    if len(res['hits']['hits']) > 0:
                        doc['validated'] = res['hits']['hits'][0]['_source']['validated']

                        if res['hits']['hits'][0]['_source']['modifiedDate_tdate'] != doc['modifiedDate_tdate']:
                            doc["records"].append({'beforeModifiedDate_tdate': doc['modifiedDate_tdate'],
                                                   'MDS': res['hits']['hits'][0]['_source']['MDS']})

                    else:
                        doc["validated"] = True
            time.sleep(1)

            res = helpers.bulk(
                es,
                docs,
                index=row["structSirene"] + "-" + row["halStructId"] + "-laboratories-documents",
            )


def collect_researchers_data():
    # initialisation liste labos supposée plus fiables que données issues Ldap.
    Labos = []
    dicoAcronym = dict()

    with open('data/laboratories.csv', encoding='utf-8') as csv_file:
        csv_reader = csv.DictReader(csv_file, delimiter=';')
        for row in csv_reader:
            row["halStructId"] = row["halStructId"].strip()
            if " " in row["halStructId"]:
                connaitLab = "non-labo"
            else:
                connaitLab = row["halStructId"]
                Labos.append(connaitLab)

            if row['acronym'] not in dicoAcronym.values():
                dicoAcronym[row['halStructId']] = row['acronym']
    print(f"labos variable values ={Labos}")

    # Process researchers
    researchers_list = []
    if csv_open:
        with open('data/researchers.csv', encoding='utf-8') as csv_file:
            csv_reader = list(csv.DictReader(csv_file, delimiter=','))
            if researchers_list:
                print("checking researchers.csv list: ")

                for searcher in csv_reader:
                    if any(dictlist['halStructId'] == searcher['halStructId'] for dictlist in researchers_list):
                        print(f'{searcher["acronym"]} is already in researchers_list')
                    else:
                        print(f'adding {searcher["acronym"]} to researchers_list')
                        researchers_list.append(searcher)
            else:
                print("researchers_list is empty, adding csv content to values")
                researchers_list = csv_reader

    if djangodb_open:
        if researchers_list:
            print("checking DjangoDb laboratory list:")
            for searcher in Researcher.objects.all().values():
                searcher.pop('id')
                if any(dictlist['halStructId'] == searcher['halStructId'] for dictlist in researchers_list):
                    print(f'{searcher["acronym"]} is already in researchers_list')
                else:
                    print(f'adding {searcher["acronym"]} to researchers_list')
                    researchers_list.append(searcher)
        else:
            print("researchers_list is empty, adding DjangoDb content to values")
            for searcher in Researcher.objects.all().values():
                searcher.pop('id')
                researchers_list.append(searcher)

    print(researchers_list)
    for row in researchers_list:
        if row["structSirene"] in structIdlist:  # seulement les chercheurs de la structure
            print(f"Processing : {row['halId_s']}")
            if row["labHalId"] not in Labos:
                row["labHalId"] = "non-labo"
            # Collect publications
            docs = hal.find_publications(row['halId_s'], 'authIdHal_s')
            docs = location_docs.generate_countrys_fields(docs)

            # Insert documents collection
            for num, doc in enumerate(docs):
                doc["_id"] = doc['docid']
                doc["validated"] = True

                doc["harvested_from"] = "researcher"

                doc["harvested_from_ids"] = []
                doc["harvested_from_label"] = []
                try:
                    doc["harvested_from_label"].append(dicoAcronym[row["labHalId"]])
                except:
                    doc["harvested_from_label"].append("non-labo")

                doc["harvested_from_ids"].append(row['halId_s'])
                # historique d'appartenance du docId
                # pour attribuer les bons docs aux chercheurs
                harvet_history.append({'docid': doc['docid'], 'from': row['halId_s']})

                for h in harvet_history:
                    if h['docid'] == doc['docid']:
                        if h['from'] not in doc["harvested_from_ids"]:
                            doc["harvested_from_ids"].append(h['from'])

                doc["records"] = []

                if 'doiId_s' in doc:
                    tmp_unpaywall = unpaywall.get_oa(doc['doiId_s'])
                    if 'is_oa' in tmp_unpaywall: doc['is_oa'] = tmp_unpaywall['is_oa']
                    if 'oa_status' in tmp_unpaywall: doc['oa_status'] = tmp_unpaywall['oa_status']
                    if 'oa_host_type' in tmp_unpaywall: doc['oa_host_type'] = tmp_unpaywall['oa_host_type']

                doc["MDS"] = utils.calculate_mds(doc)

                try:
                    shouldBeOpen = utils.should_be_open(doc)
                    if shouldBeOpen == 1:
                        doc["should_be_open"] = True
                    if shouldBeOpen == -1:
                        doc["should_be_open"] = False

                    if shouldBeOpen == 1 or shouldBeOpen == 2:
                        doc['isOaExtra'] = True
                    elif shouldBeOpen == -1:
                        doc['isOaExtra'] = False
                except:
                    print('publicationDate_tdate error ?')

                if not init:

                    doc_param = esActions.scope_p("_id", doc["_id"])

                    if not es.indices.exists(index=row["structSirene"] + "-" + row["labHalId"] + "-researchers-" + row["ldapId"] + "-documents"):  # -researchers" + row["ldapId"] + "-documents
                        print(f'exception {row["labHalId"]}, {row["ldapId"]}')
                        break
                    res = es.search(index=row["structSirene"] + "-" + row["labHalId"] + "-researchers-" + row[
                        "ldapId"] + "-documents", body=doc_param)  # -researchers" + row["ldapId"] + "-documents

                    if len(res['hits']['hits']) > 0:
                        doc['validated'] = res['hits']['hits'][0]['_source']['validated']

                        if res['hits']['hits'][0]['_source']['modifiedDate_tdate'] != doc['modifiedDate_tdate']:
                            doc["records"].append({'beforeModifiedDate_tdate': doc['modifiedDate_tdate'],
                                                   'MDS': res['hits']['hits'][0]['_source']['MDS']})

                    else:
                        doc["validated"] = True
            time.sleep(1)

            res = helpers.bulk(
                es,
                docs,
                index=row["structSirene"] + "-" + row["labHalId"] + "-researchers-" + row["ldapId"] + "-documents",
                # -researchers" + row["ldapId"] + "-documents
            )
        else:
            print(f"chercheur hors structure, {row['ldapId']}, structure : {row['structSirene']}")


def autorun(laboratories, researcher, csv_enabler=True, django_enabler=None):
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
    autorun(researcher='on', laboratories='on')
