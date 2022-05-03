import csv
import datetime
import json
import sys
import time
from decouple import config
# Custom libs
from sovisuhal.libs import esActions
from elasticHal.libs import archivesOuvertes, utils
# Global variables
structIdlist = None
Labolist = None
# Connect to DB
es = esActions.es_connector()

print(__name__)

# parameters
csv_open = None  # Si csv_open = True, prise en compte des csv pour le processus en addition des données ES. Est à True par défaut dans le cas ou le fichier est lancé en tant que script (voir en bas du code)
init = True

def get_structid_list():
    print(csv_open)
    global structIdlist
    structIdlist = []
    # get structId for already existing structures in ES
    scope_param = esActions.scope_all()
    count = es.count(index="*-structures", body=scope_param)['count']
    res = es.search(index="*-structures", body=scope_param, size=count)
    es_struct = res['hits']['hits']

    for row in es_struct:
        row = row['_source']
        structsirene = row['structSirene']
        structIdlist.append(structsirene)

    es_struct = None

    # get structId for structures in csv and compare with ES
    if csv_open:
        with open('data/structures.csv', encoding='utf-8') as csv_file:
            csv_reader = csv.DictReader(csv_file, delimiter=',')
            for csv_row in csv_reader:
                if " " in csv_row["structSirene"]:
                    print("StructSirerene missing for ", csv_row["acronym"])
                else:
                    if csv_row["structSirene"] not in structIdlist:
                        structIdlist.append(csv_row["structSirene"])
                    else:
                        print(csv_row["acronym"], " is already listed")
    print("listed structId: ")
    print(structIdlist)


def get_labo_list():
    # initialisation liste labos supposée plus fiables que données issues Ldap.
    global Labolist
    Labolist = []

    scope_param = esActions.scope_all()

    for structId in structIdlist:
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
                Labolist.append(connaitLab)
        except:
            print("exception found")
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
                    if connaitLab not in Labolist:
                        Labolist.append(connaitLab)

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


        with open('data/researchers.csv', encoding='utf-8') as csv_file:
            csv_reader = csv.DictReader(csv_file, delimiter=',')
            for row in csv_reader:
                row["labHalId"] = row["labHalId"].strip()
                if row["labHalId"] not in Labolist:
                    connaitLab = "non-labo"
                else:
                    connaitLab = row["labHalId"]  # valeur à la noix des fois
                if row["structSirene"] in structIdlist:
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
                else:
                    print("get_labo_list data/resarchers.csv create skipped for ", row["ldapId"])

    print("Labhalid listed: ")
    print(Labolist)


def process_structures():
    # Process structures
    with open('data/structures.csv', encoding='utf-8') as csv_file:
        csv_reader = csv.DictReader(csv_file, delimiter=',')
        for row in csv_reader:
            # Insert structure data
            res = es.index(index=row["structSirene"] + "-structures", id=row['structSirene'], body=json.dumps(row))


def process_researchers():
    # Process researchers
    scope_param = esActions.scope_all()

    for structId in structIdlist:
        count = es.count(index=structId + "*-researchers", body=scope_param)['count']
        res = es.search(index=structId + "*-researchers", body=scope_param, size=count)
        esResearchers = res['hits']['hits']
        cleaned_es_researchers = []
        for row in esResearchers:
            row = row['_source']
            cleaned_es_researchers.append(row)

        esResearchers = None

    if csv_open:
        with open('data/researchers.csv', encoding='utf-8') as csv_file:
            csv_reader = csv.DictReader(csv_file, delimiter=',')
            csv_reader = list(csv_reader)
            if cleaned_es_researchers:
                print("checking csv researcher list:")
                for csv_row in csv_reader:
                    if any(dictlist['aurehalId'] == csv_row['aurehalId'] for dictlist in cleaned_es_researchers):  # Si l'aurehalid de la ligne du csv (=chercheur) est présente dans les données récupérées d'ES : on ignore. Sinon on rajoute le chercheur à la liste.
                        print(print(csv_row["halId_s"] + " is already in cleaned_es_researchers"))

                    else:
                        print("adding " + csv_row["halId_s"] + " to cleaned_es_researchers")
                        cleaned_es_researchers.append(csv_row)

            else:
                print("cleaned_es_researchers is empty")
                cleaned_es_researchers = csv_reader

    for row in cleaned_es_researchers:

        if row["structSirene"] in structIdlist:
            print('Processing : ' + row['halId_s'])
            # connaitLab = row["labHalId"] # valeur à la noix des fois
            row["labHalId"] = row["labHalId"].strip()
            if 'validated' in row.keys():
                if not row["validated"]:
                    row["validated"] = False
                else:
                    row["validated"] = True
            row["Created"] = datetime.datetime.now().isoformat()
            if row['labHalId'] not in Labolist:
                oldLab = row['labHalId']
                row['labHalId'] = "non-labo"
                print('labo changé --> ', oldLab, ' en ', row['labHalId'], ' pour ', row["ldapId"])
                connaitLab = "non-labo"

            else:
                connaitLab = row["labHalId"]
                oldLab = row['labHalId']

            archivesOuvertesData = archivesOuvertes.get_concepts_and_keywords(row['aurehalId'])

            time.sleep(1)

            if "guidingKeywords" not in row:  # si le champ n'existe pas (ou vide) met la valeur à [], sinon persistance des données
                row['guidingKeywords'] = []

            if "orcId" not in row:  # si le champ n'existe pas (ou vide) met la valeur à "", sinon persistance des données
                row['orcId'] = ""

            if "validated" not in row:  # si le champ n'existe pas (ou vide) met la valeur à "", sinon persistance des données
                row['validated'] = False

            if "researchDescription" not in row:  # si le champ n'existe pas (ou vide) met la valeur à "", sinon persistance des données
                row['researchDescription'] = ''

            if "axis" not in row:
                row["axis"] = row['lab']
                print("affectations automatique d'un axis : " + row["axis"])

            validated_ids = []
            if 'concepts' in row:  # si le champ existe : mise à jour des concepts existant avec persistance des données validées, sinon création des concepts.
                if 'children' in row['concepts']:
                    for children in row['concepts']['children']:
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
            row['concepts'] = utils.filter_concepts(archivesOuvertesData['concepts'], validated_ids)

            # Insert researcher data
            if init:
                print("Process researcher init path")

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

        else:
            print('chercheur hors structure ', row['ldapId'], ", structure : ", row['structSirene'])


def process_laboratories():
    # Process laboratories
    scope_param = esActions.scope_all()

    for structId in structIdlist:
        count = es.count(index=structId + "*-laboratories", body=scope_param)['count']
        res = es.search(index=structId + "*-laboratories", body=scope_param, size=count)

        esLaboratories = res['hits']['hits']
        cleaned_es_laboratories = []

        for row in esLaboratories:
            row = row['_source']
            cleaned_es_laboratories.append(row)

        esLaboratories = None

    if csv_open:
        with open('data/laboratories.csv', encoding='utf-8') as csv_file:
            csv_reader = csv.DictReader(csv_file, delimiter=';')
            csv_reader = list(csv_reader)
            if cleaned_es_laboratories:
                print("checking csv researcher list:")
                for csv_row in csv_reader:
                    if any(dictlist['halStructId'] == csv_row['halStructId'] for dictlist in cleaned_es_laboratories):
                        print(csv_row["acronym"] + " is already in cleaned_es_laboratories")

                    else:
                        print("adding " + csv_row["acronym"] + " to cleaned_es_laboratories")
                        cleaned_es_laboratories.append(csv_row)

            else:
                print("cleaned_es_researchers is empty")
                cleaned_es_laboratories = csv_reader

    for row in cleaned_es_laboratories:
        print(row['acronym'])

        row['guidingKeywords'] = []

        # Get researchers from the laboratory
        rsr_param = esActions.scope_p("labHalId", row["halStructId"])

        es.indices.refresh(index=row['structSirene'] + "-" + row["halStructId"] + "-researchers")  # force le refresh des indices(index) de elasticsearch
        res = es.search(index=row['structSirene'] + "-" + row["halStructId"] + "-researchers", body=rsr_param)

        # Build laboratory skills
        tree = {'id': 'Concepts', 'children': []}

        for rsr in res['hits']['hits']:

            concept = rsr['_source']['concepts']

            if len(concept) > 0:

                for child in concept['children']:

                    if child['state'] == 'invalidated':
                        tree = utils.append_to_tree(child, rsr['_source'], tree, 'invalidated')
                    else:
                        tree = utils.append_to_tree(child, rsr['_source'], tree, 'validated')
                    if 'children' in child:
                        for child1 in child['children']:

                            if child1['state'] == 'invalidated':
                                tree = utils.append_to_tree(child1, rsr['_source'], tree, 'invalidated')
                            else:
                                tree = utils.append_to_tree(child1, rsr['_source'], tree, 'validated')

                            if 'children' in child1:
                                for child2 in child1['children']:

                                    if child2['state'] == 'invalidated':
                                        tree = utils.append_to_tree(child2, rsr['_source'], tree, 'invalidated')
                                    else:
                                        tree = utils.append_to_tree(child2, rsr['_source'], tree, 'validated')

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
        # create laboratory document repertory
        if not es.indices.exists(index=row['structSirene'] + "-" + row["halStructId"] + "-laboratories-documents"):
            print("creating document directory for: ", row["acronym"])
            es.indices.create(
                index=row['structSirene'] + "-" + row["halStructId"] + "-laboratories-documents")


if __name__ == '__main__':
    csv_open = True
    print(time.strftime("%H:%M:%S", time.localtime()), end=' : ')
    print('get_structid_list')
    get_structid_list()
    print(time.strftime("%H:%M:%S", time.localtime()), end=' : ')
    print('get_labo_list')
    get_labo_list()
    print(time.strftime("%H:%M:%S", time.localtime()), end=' : ')
    print('process_structures')
    process_structures()
    print(time.strftime("%H:%M:%S", time.localtime()), end=' : ')
    print('process_researchers')
    process_researchers()
    print(time.strftime("%H:%M:%S", time.localtime()), end=' : ')
    print('process_laboratories')
    process_laboratories()
    print(time.strftime("%H:%M:%S", time.localtime()), end=' : ')
    print('harvesting finished')
