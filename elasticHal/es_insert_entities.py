import csv
import datetime
import json
import sys
import time

from decouple import config

# Custom libs
from sovisuhal.libs import esActions
from elasticHal.libs import archivesOuvertes, utils


if __name__ == '__main__':

    init = True  # Si Init = True, prise en compte des csv pour le processus en addition des données ES.
    try:
        structId = config("structId")
    except:
        structId = "198307662"  # UTLN
    print(time.strftime("%H:%M:%S", time.localtime()), end=' : ')
    print('harvesting started')

    # Parameters
    # Connect to DB
    es = esActions.es_connector()

    # initialisation liste labos supposée plus fiables que données issues Ldap.
    Labos = []

    scope_param = esActions.scope_all()

    count = es.count(index=structId + "*-laboratories", body=scope_param)['count']
    res = es.search(index=structId + "*-laboratories", body=scope_param, size=count)

    esLaboratories = res['hits']['hits']

    for row in esLaboratories:
        row = row['_source']
        try:
            if " " in row["halStructId"]:
                connaitLab = "non-labo"
            else:
                connaitLab = row["halStructId"]
                Labos.append(connaitLab)
        except:
            print(row)
            sys.exit(1)

    if init:
        with open('data/laboratories.csv', encoding='utf-8') as csv_file:
            csv_reader = csv.DictReader(csv_file, delimiter=';')
            for row in csv_reader:
                row["validated"] = False
                row["halStructId"] = row["halStructId"].strip()
                if " " in row["halStructId"]:
                    print('couac in labo Id : ', row["halStructId"])
                    connaitLab = "non-labo"
                else:
                    connaitLab = row["halStructId"]
                    if connaitLab not in Labos:
                        Labos.append(connaitLab)

                if not es.indices.exists(index=row['structSirene'] + "-" + row["halStructId"] + "-laboratories"):
                    try:
                        es.indices.create(index=row['structSirene'] + "-" + row["halStructId"] + "-laboratories")
                    except:
                        print("devrait pas passer par là, couac labo encore ?", row["halStructId"])
                        connaitLab = "non-labo"

                        if not es.indices.exists(index=row['structSirene'] + "-" + connaitLab + "-laboratories"):
                            es.indices.create(index=row['structSirene'] + "-" + connaitLab + "-laboratories")
                if not es.indices.exists(index=row['structSirene'] + "-structures"):
                    es.indices.create(index=row['structSirene'] + "-structures")
                if not es.indices.exists(index=row['structSirene'] + "-" + connaitLab + "-researchers"):
                    es.indices.create(index=row['structSirene'] + "-" + connaitLab + "-researchers")
                    # es.indices.create(index=row["structSirene"] + "-" + connaitLab + "-researchers-documents") # ou devrait être fait en fonction de l'Id chercheur ?
        with open('data/researchers.csv', encoding='utf-8') as csv_file:
            csv_reader = csv.DictReader(csv_file, delimiter=',')
            for row in csv_reader:
                row["labHalId"] = row["labHalId"].strip()
                if row["labHalId"] not in Labos:
                    connaitLab = "non-labo"
                else:
                    connaitLab = row["labHalId"]  # valeur à la noix des fois
                if row["structSirene"] == structId:
                    if not es.indices.exists(index=row["structSirene"] + "-" + connaitLab + "-laboratories"):
                        try:
                            es.indices.create(index=row["structSirene"] + "-" + connaitLab + "-laboratories")
                        except:
                            connaitLab = "non-labo"  # devrait jamais être là
                            if not es.indices.exists(index=row["structSirene"] + "-" + connaitLab + "-laboratories"):
                                es.indices.create(index=row["structSirene"] + "-" + connaitLab + "-laboratories")
                    if not es.indices.exists(index=row["structSirene"] + "-structures"):
                        es.indices.create(index=row["structSirene"] + "-structures")
                    if not es.indices.exists(index=row["structSirene"] + "-" + connaitLab + "-researchers"):
                        es.indices.create(index=row["structSirene"] + "-" + connaitLab + "-researchers")
                        es.indices.create(index=row["structSirene"] + "-" + connaitLab + "-researchers-" + row[
                            "ldapId"] + "-documents")  # -researchers" + row["ldapId"] + "-documents
                    else:
                        if not es.indices.exists(index=row["structSirene"] + "-" + connaitLab + "-researchers-" + row["ldapId"] + "-documents"):
                            es.indices.create(index=row["structSirene"] + "-" + connaitLab + "-researchers-" + row["ldapId"] + "-documents")  # -researchers" + row["ldapId"] + "-documents" ?

        # Process structures
        with open('data/structures.csv', encoding='utf-8') as csv_file:
            csv_reader = csv.DictReader(csv_file, delimiter=',')
            for row in csv_reader:
                # Insert structure data
                res = es.index(index=row["structSirene"] + "-structures", id=row['structSirene'], body=json.dumps(row))

    # Process researchers

    scope_param = esActions.scope_all()

    count = es.count(index=structId + "*-researchers", body=scope_param)['count']
    res = es.search(index=structId + "*-researchers", body=scope_param, size=count)
    esResearchers = res['hits']['hits']
    cleaned_es_researchers = []
    for row in esResearchers:
        row = row['_source']
        cleaned_es_researchers.append(row)

    esResearchers = None

    if init:
        with open('data/researchers.csv', encoding='utf-8') as csv_file:
            csv_reader = csv.DictReader(csv_file, delimiter=',')
            csv_reader = list(csv_reader)
            if cleaned_es_researchers:
                print("checking csv researcher list:")
                for csv_row in csv_reader:
                    if any(dictlist['aurehalId'] == csv_row['aurehalId'] for dictlist in cleaned_es_researchers):
                        print(print(csv_row["halId_s"] + " is already in cleaned_es_researchers"))

                    else:
                        print("adding " + csv_row["halId_s"] + " to cleaned_es_researchers")
                        cleaned_es_researchers.append(csv_row)

            else:
                print("cleaned_es_researchers is empty")
                cleaned_es_researchers = csv_reader

    for row in cleaned_es_researchers:

        if row["structSirene"] == structId:
            print('Processing : ' + row['halId_s'])
            # connaitLab = row["labHalId"] # valeur à la noix des fois
            row["labHalId"] = row["labHalId"].strip()
            if 'validated' in row.keys():
                if not row["validated"]:
                    row["validated"] = False
                else:
                    row["validated"] = True
            row["Created"] = datetime.datetime.now().isoformat()
            if row['labHalId'] not in Labos:
                oldLab = row['labHalId']
                row['labHalId'] = "non-labo"
                print('labo changé --> ', oldLab, ' en ', row['labHalId'], ' pour ', row["ldapId"])
                connaitLab = "non-labo"

            else:
                connaitLab = row["labHalId"]
                oldLab = row['labHalId']
            # if not es.indices.exists(index=row["structSirene"]+"-" + row["labHalId"]+"-laboratories"):
            #         try:
            #             es.indices.create(index=row["structSirene"]+"-" + row["labHalId"]+"-laboratories")
            #         except:
            #             connaitLab = "Nan"
            # if not es.indices.exists(index=row["structSirene"] + "-" + connaitLab + "-laboratories"):
            #     es.indices.create(index=row["structSirene"] + "-" + connaitLab + "-laboratories")
            # if not es.indices.exists(index=row["structSirene"]+"-structures"):
            #     es.indices.create(index=row["structSirene"]+"-structures")
            # if not es.indices.exists(index=row["structSirene"]+"-" + connaitLab+"-researchers"):
            #     es.indices.create(index=row["structSirene"]+"-" + connaitLab+"-researchers")
            archivesOuvertesData = archivesOuvertes.get_concepts_and_keywords(row['aurehalId'])
            # for sirene in row['structSirene'].split(','):
            #     if len(sirene) > 1:
            time.sleep(1)

            if not init:
                # Get researcher data
                rsr_param = esActions.scope_p("ldapId", row["ldapId"])

                if row['labHalId'] != "non-labo":
                    res = es.search(index=row["structSirene"] + "-" + connaitLab + "-researchers", body=rsr_param)
                else:
                    res = es.search(index=row["structSirene"] + "-" + row['labHalId'] + "-researchers", body=rsr_param)
                try:
                    rsr_prev = res['hits']['hits'][0]['_source']
                except:
                    print(res['hits']['hits'])
                    sys.exit(0)
                row['validated'] = rsr_prev['validated']
                if 'idRef' in rsr_prev:
                    row['idRef'] = rsr_prev['idRef']
                if 'orcId' in rsr_prev:
                    row['orcId'] = rsr_prev['orcId']
                if 'lab' in rsr_prev:
                    if len(rsr_prev['lab']) > 0:
                        row['lab'] = rsr_prev['lab']
                    else:
                        row['lab'] = connaitLab  # ?
                else:
                    row['lab'] = connaitLab  # ?

                validated_ids = []

                if 'researchDescription' in rsr_prev:
                    row['researchDescription'] = rsr_prev['researchDescription']
                else:
                    row['researchDescription'] = ''
                if len(rsr_prev['guidingKeywords']):
                    row['guidingKeywords'] = rsr_prev['guidingKeywords']
                else:
                    row['guidingKeywords'] = []

                if 'children' in rsr_prev['concepts']:
                    for children in rsr_prev['concepts']['children']:
                        if children['state'] == 'validated':
                            validated_ids.append(children['id'])
                        if 'children' in children:
                            for children1 in children['children']:
                                if children1['state'] == 'validated':
                                    validated_ids.append(children1['id'])
                                if 'children' in children1:
                                    for children2 in children1['children']:
                                        if children2['state'] == 'validated':
                                            validated_ids.append(children2['id'])

                print(validated_ids)

                row['concepts'] = utils.filter_concepts(archivesOuvertesData['concepts'], validated_ids)

            else:
                row['concepts'] = utils.filter_concepts(archivesOuvertesData['concepts'], validated_ids=[])

            if "axis" not in row:
                row["axis"] = row['lab']
                print("affectations automatique d'un axis : " + row["axis"])

            # row['keywords'] = archivesOuvertesData['keywords']

            # row['concepts'] = []
            # row['keywords'] = []

            # pourquoi ils sont réinitialisés (et dans tous les cas init) eux  ? :
            # row['guidingKeywords'] = []

            # Insert researcher data

            if init:
                res = es.index(index=row['structSirene'] + "-" + connaitLab + "-researchers", id=row['ldapId'],
                               body=json.dumps(row))
            else:
                # print("row : ", row)
                print("index : ", row['structSirene'] + "-" + connaitLab + "-researchers")
                if not es.indices.exists(index=row["structSirene"] + "-" + connaitLab + "-researchers"):
                    es.indices.create(index=row["structSirene"] + "-" + connaitLab + "-researchers")
                    es.indices.create(index=row["structSirene"] + "-" + connaitLab + "-researchers-" + row[
                        "ldapId"] + "-documents")  # -researchers" + row["ldapId"] + "-documents
                    res = es.index(index=row['structSirene'] + "-" + connaitLab + "-researchers", id=row['ldapId'],
                                   body=json.dumps(row))
                elif not es.indices.exists(index=row["structSirene"] + "-" + connaitLab + "-researchers-" + row["ldapId"] + "-documents"):
                    es.indices.create(index=row["structSirene"] + "-" + connaitLab + "-researchers-" + row["ldapId"] + "-documents")  # -researchers" + row["ldapId"] + "-documents" ?
                else:
                    try:
                        docu = dict()  # from https://stackoverflow.com/questions/57564374/elasticsearch-update-gives-unknown-field-error
                        docu["doc"] = row  # MAIS : https://github.com/elastic/elasticsearch-py/issues/1698
                        res = es.update(index=row['structSirene'] + "-" + connaitLab + "-researchers", id=row['ldapId'],
                                        body=json.dumps(docu))
                    except:
                        print("changement d'index : ", connaitLab)
                        print(row)
                        try:
                            res = es.index(index=row['structSirene'] + "-" + connaitLab + "-researchers", id=row['ldapId'], body=json.dumps(row))
                        except:
                            print("boum 2 ???", connaitLab, row['ldapId'])
                if connaitLab != oldLab:
                    print(" détruire l'entrée ", row['structSirene'] + "-" + oldLab + "-researchers/" + row['ldapId'])

                    # sys.exit()
        else:
            print('chercheur hors structure ', row['ldapId'], ", structure : ", row['structSirene'])

    # Process laboratories
    scope_param = esActions.scope_all()

    count = es.count(index=structId + "*-laboratories", body=scope_param)['count']
    res = es.search(index=structId + "*-laboratories", body=scope_param, size=count)

    esLaboratories = res['hits']['hits']
    cleaned_es_laboratories = []

    for row in esLaboratories:
        row = row['_source']
        cleaned_es_laboratories.append(row)

    esLaboratories = None

    if init:
        with open('data/laboratories.csv', encoding='utf-8') as csv_file:
            csv_reader = csv.DictReader(csv_file, delimiter=';')
            csv_reader = list(csv_reader)
            if cleaned_es_laboratories:
                print("checking csv researcher list:")
                for csv_row in csv_reader:
                    if any(dictlist['halStructId'] == csv_row['halStructId'] for dictlist in cleaned_es_laboratories):
                        print(print(csv_row["acronym"] + " is already in cleaned_es_laboratories"))

                    else:
                        print("adding " + csv_row["acronym"] + " to cleaned_es_laboratories")
                        cleaned_es_laboratories.append(csv_row)

            else:
                print("cleaned_es_researchers is empty")
                cleaned_es_laboratories = csv_reader

    for row in cleaned_es_laboratories:
        print(row['acronym'])

        row['guidingKeywords'] = []

        # tmp_sirenes = []
        # for sirene in row['structSirene'].split(','):
        #     tmp_sirenes.append(sirene) # useless ?

        # row['structSirene'] = list(tmp_sirenes)

        # Get researchers from the laboratory
        rsr_param = esActions.scope_p("labHalId", row["halStructId"])

        es.indices.refresh(index=row['structSirene'] + "-" + row["halStructId"] + "-researchers")  # force le refresh des indices(index) de elasticsearch
        res = es.search(index=row['structSirene'] + "-" + row["halStructId"] + "-researchers", body=rsr_param)

        concepts = []

        # Build laboratory skills
        tree = {'id': 'Concepts', 'children': []}

        for rsr in res['hits']['hits']:

            concept = rsr['_source']['concepts']

            if len(concept) > 0:

                for child in concept['children']:

                    if child['state'] == 'invalidated':
                        tree = utils.append_to_tree(child, rsr['_source'], tree, 'invalidated')
                    else:
                        tree = utils.append_to_tree(child, rsr['_source'], tree)
                    if 'children' in child:
                        for child1 in child['children']:

                            if child1['state'] == 'invalidated':
                                tree = utils.append_to_tree(child1, rsr['_source'], tree, 'invalidated')
                            else:
                                tree = utils.append_to_tree(child1, rsr['_source'], tree)

                            if 'children' in child1:
                                for child2 in child1['children']:

                                    if child2['state'] == 'invalidated':
                                        tree = utils.append_to_tree(child2, rsr['_source'], tree, 'invalidated')
                                    else:
                                        tree = utils.append_to_tree(child2, rsr['_source'], tree)

        row["Created"] = datetime.datetime.now().isoformat()
        row['concepts'] = tree

        # Insert laboratory data
        if init:
            res = es.index(index=row['structSirene'] + "-" + row["halStructId"] + "-laboratories",
                           id=row['halStructId'], body=json.dumps(row))
        else:
            docu = dict()  # from https://stackoverflow.com/questions/57564374/elasticsearch-update-gives-unknown-field-error
            docu["doc"] = row
            res = es.update(index=row['structSirene'] + "-" + row["halStructId"] + "-laboratories",
                            id=row['halStructId'], body=json.dumps(docu))
            try:
                pass
            except:
                import pprint as pp

                print('NON mis à jour')
                pp.pprint(row)
                print(row['structSirene'] + "-" + row["halStructId"] + "-laboratories")
                sys.exit()

print(time.strftime("%H:%M:%S", time.localtime()), end=' : ')
print('harvesting finished')
