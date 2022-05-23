import datetime
import time
from elasticsearch import helpers
# Custom libs
from sovisuhal.libs import esActions
from elasticHal.libs import hal, utils, unpaywall, archivesOuvertes, location_docs, doi_enrichissement

# Global variables
init = False
force_hal = True
forceAuthorship = True

# Connect to DB
es = esActions.es_connector()
# get structId for already existing structures in ES
scope_param = esActions.scope_all()
res = es.search(index="*-structures", body=scope_param, filter_path=["hits.hits._source.structSirene"])

structIdlist = [hit['_source']['structSirene'] for hit in res['hits']['hits']]
print(structIdlist)
if __name__ == '__main__':

    harvet_history = []

    print(time.strftime("%H:%M:%S", time.localtime()), end=' : ')
    print('harvesting started')

    # Process laboratories
    # astuce pour passer vite
    dicoAcronym = dict()

    scope_param = esActions.scope_all()

    # init esLaboratories
    count = es.count(index="*-laboratories", body=scope_param)['count']
    res = es.search(index="*-laboratories", body=scope_param, size=count)
    esLaboratories = res['hits']['hits']

    for row in esLaboratories:
        row = row['_source']
        print('Processing : ' + row['acronym'])
        # Collect publications
        if len(row['halStructId']) > 0:
            docs = hal.find_publications(row['halStructId'], 'labStructId_i')
            # Enrichssements des documents récoltés
            docs = location_docs.generate_countrys_fields(docs)
            docs = doi_enrichissement.docs_enrichissement_doi(docs)
            

            # Insert documents collection
            for num, doc in enumerate(docs):
                # print('- sub processing : ' + str(doc['docid']))
                doc["_id"] = doc['docid']
                doc["validated"] = True
                doc["harvested_from"] = "lab"
                doc["harvested_from_ids"] = []

                doc["harvested_from_ids"].append(row['halStructId'])
                doc["harvested_from_label"] = []
                doc["harvested_from_label"].append(row['acronym'])
                if "Created" not in doc:
                    doc['Created'] = datetime.datetime.now().isoformat()
                # Pour @Joseph
                # nlp = tal(doc ['abstract']) # trouver le bon champ
                # doc["Entites"] = [entity for entity in nlp.ents] # Entites Nommées
                # doc["AbstractNettoye"] = [mot for mot nlp if mot not in doc["Entites"] ] # mots du résumé non

                doc["authorship"] = []

                authHalId_s_filled = []
                if "authId_i" in doc:
                    for auth in doc["authId_i"]:
                        try:
                            aureHal = archivesOuvertes.get_halid_s(auth)
                            authHalId_s_filled.append(aureHal)
                        except:
                            authHalId_s_filled.append("")

                authors_count = len(authHalId_s_filled)
                i = 0
                for auth in authHalId_s_filled:
                    i += 1
                    if i == 1 and auth != "":
                        doc["authorship"].append({"authorship": "firstAuthor", "authFullName_s": auth})
                    elif i == authors_count and auth != "":
                        doc["authorship"].append({"authorship": "lastAuthor", "authFullName_s": auth})

                harvet_history.append({'docid': doc['docid'], 'from': row['halStructId']})

                for h in harvet_history:
                    if h['docid'] == doc['docid']:
                        doc["harvested_from_ids"].append(h['from'])
                """
                if 'doiId_s' in doc:
                    tmp_unpaywall = unpaywall.get_oa(doc['doiId_s'])
                    if 'is_oa' in tmp_unpaywall: doc['is_oa'] = tmp_unpaywall['is_oa']
                    if 'oa_status' in tmp_unpaywall: doc['oa_status'] = tmp_unpaywall['oa_status']
                    if 'oa_host_type' in tmp_unpaywall: doc['oa_host_type'] = tmp_unpaywall['oa_host_type']
                """
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
                    res = es.search(index=row["structSirene"] + "-" + row["halStructId"] + "-laboratories-documents",
                                    body=doc_param)

                    if len(res['hits']['hits']) > 0:
                        if "authorship" in res['hits']['hits'][0]['_source'] and not forceAuthorship:
                            doc["authorship"] = res['hits']['hits'][0]['_source']['authorship']
                        if "validated" in res['hits']['hits'][0]['_source']:
                            doc['validated'] = res['hits']['hits'][0]['_source']['validated']
                        if force_hal:
                            doc['validated'] = True

                        if res['hits']['hits'][0]['_source']['modifiedDate_tdate'] != doc['modifiedDate_tdate']:
                            doc["records"].append({'beforeModifiedDate_tdate': doc['modifiedDate_tdate'],
                                                   'MDS': res['hits']['hits'][0]['_source']['MDS']})

                    else:
                        doc["validated"] = True

            res = helpers.bulk(
                es,
                docs,
                index=row["structSirene"] + "-" + row["halStructId"] + "-laboratories-documents",
            )

            print(res)

    # initialisation liste labos supposée plus fiables que données issues Ldap.
    Labos = []
    for row in esLaboratories:
        row = row['_source']
        row["halStructId"] = row["halStructId"].strip()
        if " " in row["halStructId"]:
            connaitLab = "non-labo"
        else:
            connaitLab = row["halStructId"]
            Labos.append(connaitLab)
        if row['acronym'] not in dicoAcronym.values():
            dicoAcronym[row['halStructId']] = row['acronym']
    # Process researchers
    print(Labos)
    scope_param = esActions.scope_all()

    count = es.count(index="*-researchers", body=scope_param)['count']
    res = es.search(index="*-researchers", body=scope_param, size=count)
    esResearchers = res['hits']['hits']

    for row in esResearchers:
        row = row['_source']
        if row["structSirene"] in structIdlist:  # seulement les chercheurs des structures recensées
            print('Processing : ' + row['halId_s'])
            if row["labHalId"] not in Labos:
                row["labHalId"] = "non-labo"
            # Collect publications
            docs = hal.find_publications(row['halId_s'], 'authIdHal_s')
            #Enrichssements des documents récoltés
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
                    doc["harvested_from_label"].append(dicoAcronym[row["labHalId"]])
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
                doc["harvested_from_ids"].append(row['halId_s'])
                # historique d'appartenance du docId
                # pour attribuer les bons docs aux chercheurs
                harvet_history.append({'docid': doc['docid'], 'from': row['halId_s']})

                for h in harvet_history:
                    if h['docid'] == doc['docid']:
                        if h['from'] not in doc["harvested_from_ids"]:
                            doc["harvested_from_ids"].append(h['from'])

                doc["records"] = []
                """
                if 'doiId_s' in doc:
                    tmp_unpaywall = unpaywall.get_oa(doc['doiId_s'])
                    if 'is_oa' in tmp_unpaywall: doc['is_oa'] = tmp_unpaywall['is_oa']
                    if 'oa_status' in tmp_unpaywall: doc['oa_status'] = tmp_unpaywall['oa_status']
                    if 'oa_host_type' in tmp_unpaywall: doc['oa_host_type'] = tmp_unpaywall['oa_host_type']
                """
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
                        print("exception ", row["labHalId"], row["ldapId"])
                        break
                    res = es.search(index=row["structSirene"] + "-" + row["labHalId"] + "-researchers-" + row[
                        "ldapId"] + "-documents", body=doc_param)  # -researchers" + row["ldapId"] + "-documents

                    if len(res['hits']['hits']) > 0:
                        if "authorship" in res['hits']['hits'][0]['_source'] and not forceAuthorship:
                            doc["authorship"] = res['hits']['hits'][0]['_source']['authorship']
                        if "validated" in res['hits']['hits'][0]['_source']:
                            doc['validated'] = res['hits']['hits'][0]['_source']['validated']
                        if force_hal:
                            doc['validated'] = True

                        if res['hits']['hits'][0]['_source']['modifiedDate_tdate'] != doc['modifiedDate_tdate']:
                            doc["records"].append({'beforeModifiedDate_tdate': doc['modifiedDate_tdate'],
                                                   'MDS': res['hits']['hits'][0]['_source']['MDS']})

            res = helpers.bulk(
                es,
                docs,
                index=row["structSirene"] + "-" + row["labHalId"] + "-researchers-" + row["ldapId"] + "-documents",
                # -researchers" + row["ldapId"] + "-documents
            )
        else:
            print('chercheur hors structure ', row['ldapId'], ", structure : ", row['structSirene'])

    print(time.strftime("%H:%M:%S", time.localtime()), end=' : ')
    print('harvesting finished')
