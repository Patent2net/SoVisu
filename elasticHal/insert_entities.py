import csv
import datetime
import json
import sys
import time

# Custom libs
from sovisuhal.libs import esActions
from elasticHal.libs import archivesOuvertes, utils

"""
django_init allow to run the script by using the Database integrated in django(SQLite) without passing by SoVisu.
Turn django_init value at "True" only if you intend to use the script as standalone and want to use the Database by turning djangodb_open value at "True".
Default Value: "django_init = False"
"""
django_init = False
if __name__ == '__main__':
    if django_init:
        print("init django DB access (standalone mode)")
        import os
        import django
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sovisuhal.settings")
        django.setup()  # allow to use the elastichal.models under independantly from Django

        from elasticHal.models import Structure, Laboratory, Researcher
else:
    from elasticHal.models import Structure, Laboratory, Researcher

# Global variables declaration
structIdlist = []  # is dependant of get_structid_list()
Labolist = []

csv_open = None  # If csv_open = True script will use .csv stocked in elasticHal > data to generate index for ES. Default Value is True when used as a script and False when called by SoVisu.(check the code at the bottom of the file)
djangodb_open = None  # If djangodb_open = True script will use django Db to generate index for ES. Default Value is False vhen used as a script and True when called by SoVisu. (check the code at the bottom of the file)

init = True


# Connect to DB
es = esActions.es_connector()

# print("__name__ value is : ", __name__)


def get_structid_list():
    print("\u00A0 \u21D2 csv_open value is : ", csv_open)
    print("\u00A0 \u21D2 djangodb_open value is : ", djangodb_open)
    global structIdlist

    # get structId for already existing structures in ES
    scope_param = esActions.scope_all()
    count = es.count(index="*-structures", body=scope_param)['count']
    if count > 0:
        print("\u00A0 \u21D2 ", count, " structures found in ES")
        res = es.search(index="*-structures", body=scope_param, filter_path=["hits.hits._source.structSirene"])
        structIdlist = [hit['_source']['structSirene'] for hit in res['hits']['hits']]

    # get structId for structures in csv and compare with structIdlist
    if csv_open:
        with open('data/structures.csv', encoding='utf-8') as csv_file:
            csv_reader = csv.DictReader(csv_file, delimiter=',')
            for csv_row in csv_reader:
                if " " in csv_row["structSirene"]:
                    print("\u00A0 \u21D2 StructSirerene missing for ", csv_row["acronym"])
                else:
                    if csv_row["structSirene"] not in structIdlist:
                        structIdlist.append(csv_row["structSirene"])
                        print(f"\u00A0 \u21D2 Rajout de la structure  {csv_row['acronym']} (structSirene: {csv_row['structSirene']}) dans structIdlist")
                    else:
                        print(f"\u00A0 \u21D2 {csv_row['acronym']} is already listed (structSirene: {csv_row['structSirene']})")

    # get structId for structures in django db and compare with structIdlist
    if djangodb_open:
        for structure in Structure.objects.all():
            if structure.structSirene not in structIdlist:
                structIdlist.append(structure.structSirene)
                print("\u00A0 \u21D2 Rajout de la structure ", structure.acronym, " (", structure.structSirene, ") dans structIdlist")
            else:
                print("\u00A0 \u21D2 ", structure.acronym, " is already listed")


def get_labo_list():
    # initialisation liste labos supposée plus fiables que données issues Ldap.
    global Labolist

    scope_param = esActions.scope_all()

    es_laboratories = []
    for struct_id in structIdlist:
        count = es.count(index=struct_id + "*-laboratories", body=scope_param)['count']
        res = es.search(index=struct_id + "*-laboratories", body=scope_param, size=count)

        es_laboratories = res['hits']['hits']

    for row in es_laboratories:
        row = row['_source']
        try:
            if " " in row["halStructId"]:
                print(f"Please check {row['acronym']}({row['structSirene']}) in elastic, halStructId value is missing")
            else:
                connait_lab = row["halStructId"]
                Labolist.append(connait_lab)
        except:
            print("exception found")
            print(row)
            sys.exit(1)

    if csv_open:
        with open('data/laboratories.csv', encoding='utf-8') as csv_file:
            csv_reader = csv.DictReader(csv_file, delimiter=';')
            for row in csv_reader:
                temp_laboratories(row)

    print(f"\u00A0 \u21D2 Labhalid listed: {Labolist}")
    print(f"\u00A0 \u21D2 structid listed: {structIdlist}")
    if djangodb_open:
        for row in Laboratory.objects.all().values():
            row.pop('id')
            temp_laboratories(row)


def create_structures_index():
    # Process structures
    if csv_open:
        with open('data/structures.csv', encoding='utf-8') as csv_file:
            csv_reader = csv.DictReader(csv_file, delimiter=',')
            for row in csv_reader:
                # Insert structure data
                es.index(index=row["structSirene"] + "-structures", id=row['structSirene'], body=json.dumps(row))

    elif djangodb_open:
        for row in Structure.objects.all().values():
            row.pop('id')  # delete unique id added by django DB from the dict
            print(row)
            es.index(index=row["structSirene"] + "-structures", id=row['structSirene'], body=json.dumps(row))

    else:
        print("No source enabled to add structure. Please check the parameters")


def create_researchers_index():
    # Process researchers
    scope_param = esActions.scope_all()

    cleaned_es_researchers = []
    for structid in structIdlist:
        count = es.count(index=structid + "*-researchers", body=scope_param)['count']
        res = es.search(index=structid + "*-researchers", body=scope_param, size=count)
        es_researchers = res['hits']['hits']
        for row in es_researchers:
            row = row['_source']
            cleaned_es_researchers.append(row)

    if csv_open:
        with open('data/researchers.csv', encoding='utf-8') as csv_file:
            csv_reader = list(csv.DictReader(csv_file, delimiter=','))
            csv_reader = [searcher for searcher in csv_reader if searcher['halId_s'] != '']  # Only keep researchers with known 'halId_s'
            if cleaned_es_researchers:
                print("\u00A0 \u21D2 checking csv researcher list:")
                for csv_row in csv_reader:
                    if any(dictlist['halId_s'] == csv_row['halId_s'] for dictlist in cleaned_es_researchers):  # Si l'aurehalid de la ligne du csv (=chercheur) est présente dans les données récupérées d'ES : on ignore. Sinon on rajoute le chercheur à la liste.
                        print(f"\u00A0 \u21D2 {csv_row['halId_s']} is already in cleaned_es_researchers")

                    else:
                        print("\u00A0 \u21D2 adding " + csv_row["halId_s"] + " to cleaned_es_researchers")
                        cleaned_es_researchers.append(csv_row)

            else:
                print("\u00A0 \u21D2 cleaned_es_researchers is empty, adding csv content to values")
                cleaned_es_researchers = csv_reader

    if djangodb_open:
        django_researchers = Researcher.objects.all().values()
        django_researchers = list([researcher for researcher in django_researchers if researcher['halId_s'] != '' and researcher.pop('id')])  # Only keep researchers with known 'halId_s' and remove the 'id' value created by Django_DB
        if cleaned_es_researchers:
            for researcher in django_researchers:
                print(researcher)
                if any(dictlist['halId_s'] == researcher["halId_s"] for dictlist in cleaned_es_researchers):
                    print("\u00A0 \u21D2 ", researcher["halId_s"] + " is already in cleaned_es_researchers")
                else:
                    print("\u00A0 \u21D2 adding " + researcher["halId_s"] + " to cleaned_es_researchers")
                    cleaned_es_researchers.append(researcher)
        else:
            print("\u00A0 \u21D2 cleaned_es_researchers is empty, adding djangoDb content to values")
            cleaned_es_researchers = django_researchers

    for row in cleaned_es_researchers:

        if row["structSirene"] in structIdlist:
            print('\u00A0 \u21D2 Processing : ' + row['halId_s'])
            row["labHalId"] = row["labHalId"].strip()
            if 'validated' in row.keys():
                if not row["validated"]:
                    row["validated"] = False
                else:
                    row["validated"] = True
            row["Created"] = datetime.datetime.now().isoformat()
            if row['labHalId'] not in Labolist:
                old_lab = row['labHalId']
                row['labHalId'] = "non-labo"
                print('labo changé --> ', old_lab, ' en ', row['labHalId'], ' pour ', row["ldapId"])
                connait_lab = "non-labo"

            else:
                connait_lab = row["labHalId"]
                old_lab = row['labHalId']

            row['aurehalId'] = row['aurehalId'].strip()  # supprime les '\r' empéchant une erreur venant de SPARQL
            archives_ouvertes_data = archivesOuvertes.get_concepts_and_keywords(row['aurehalId'])

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
            row['concepts'] = utils.filter_concepts(archives_ouvertes_data['concepts'], validated_ids)

            # Insert researcher data
            if init:
                print("\u00A0 \u21D2 Process researcher init path")

                es.index(index=row['structSirene'] + "-" + connait_lab + "-researchers", id=row['ldapId'],
                         body=json.dumps(row))
            else:
                # print("row : ", row)
                print("index : ", row['structSirene'] + "-" + connait_lab + "-researchers")
                if not es.indices.exists(index=row["structSirene"] + "-" + connait_lab + "-researchers"):
                    es.indices.create(index=row["structSirene"] + "-" + connait_lab + "-researchers")
                    es.indices.create(index=row["structSirene"] + "-" + connait_lab + "-researchers-" + row[
                        "ldapId"] + "-documents")  # -researchers" + row["ldapId"] + "-documents
                    es.index(index=row['structSirene'] + "-" + connait_lab + "-researchers", id=row['ldapId'],
                             body=json.dumps(row))
                elif not es.indices.exists(index=row["structSirene"] + "-" + connait_lab + "-researchers-" + row["ldapId"] + "-documents"):
                    es.indices.create(index=row["structSirene"] + "-" + connait_lab + "-researchers-" + row["ldapId"] + "-documents")  # -researchers" + row["ldapId"] + "-documents" ?
                else:
                    try:
                        docu = dict()  # from https://stackoverflow.com/questions/57564374/elasticsearch-update-gives-unknown-field-error
                        docu["doc"] = row  # MAIS : https://github.com/elastic/elasticsearch-py/issues/1698
                        es.update(index=row['structSirene'] + "-" + connait_lab + "-researchers", id=row['ldapId'],
                                  body=json.dumps(docu))
                    except:
                        print("changement d'index : ", connait_lab)
                        print(row)
                        try:
                            es.index(index=row['structSirene'] + "-" + connait_lab + "-researchers", id=row['ldapId'], body=json.dumps(row))
                        except:
                            print("boum 2 ???", connait_lab, row['ldapId'])
                if connait_lab != old_lab:
                    print(" détruire l'entrée ", row['structSirene'] + "-" + old_lab + "-researchers/" + row['ldapId'])

            if not es.indices.exists(index=row["structSirene"] + "-" + connait_lab + "-researchers-" + row["ldapId"] + "-documents"):
                es.indices.create(index=row["structSirene"] + "-" + connait_lab + "-researchers-" + row["ldapId"] + "-documents")

            if not es.indices.exists(index=row["structSirene"] + "-" + connait_lab + "-laboratories"):
                es.indices.create(index=row["structSirene"] + "-" + connait_lab + "-laboratories")
                es.indices.create(index=row["structSirene"] + "-" + connait_lab + "-laboratories-documents")

        else:
            print('\u00A0 \u21D2 chercheur hors structure ', row['ldapId'], ", structure : ", row['structSirene'])


def create_laboratories_index():
    # Process laboratories
    scope_param = esActions.scope_all()

    cleaned_es_laboratories = []
    for structid in structIdlist:
        count = es.count(index=structid + "*-laboratories", body=scope_param)['count']
        res = es.search(index=structid + "*-laboratories", body=scope_param, size=count)

        es_laboratories = res['hits']['hits']

        for row in es_laboratories:
            row = row['_source']
            cleaned_es_laboratories.append(row)

    if csv_open:
        with open('data/laboratories.csv', encoding='utf-8') as csv_file:
            csv_reader = list(csv.DictReader(csv_file, delimiter=';'))
            if cleaned_es_laboratories:
                print("\u00A0 \u21D2 checking csv researcher list:")
                for csv_row in csv_reader:
                    if any(dictlist['halStructId'] == csv_row['halStructId'] for dictlist in cleaned_es_laboratories):
                        print("\u00A0 \u21D2 ", csv_row["acronym"] + " is already in cleaned_es_laboratories")

                    else:
                        print("\u00A0 \u21D2 adding " + csv_row["acronym"] + " to cleaned_es_laboratories")
                        cleaned_es_laboratories.append(csv_row)

            else:
                print("\u00A0 \u21D2 cleaned_es_laboratories is empty, adding csv content to values")
                cleaned_es_laboratories = csv_reader

    if djangodb_open:
        if cleaned_es_laboratories:
            print("\u00A0 \u21D2 checking DjangoDb laboratory list:")
            for lab in Laboratory.objects.all().values():
                lab.pop('id')
                if any(dictlist['halStructId'] == lab['halStructId'] for dictlist in cleaned_es_laboratories):
                    print(lab["acronym"] + " is already in cleaned_es_laboratories")

                else:
                    print("\u00A0 \u21D2 adding " + lab["acronym"] + " to cleaned_es_laboratories")
                    cleaned_es_laboratories.append(lab)

        else:
            print("\u00A0 \u21D2 cleaned_es_laboratories is empty, adding djangoDb content to values")
            for lab in Laboratory.objects.all().values():
                lab.pop('id')
                cleaned_es_laboratories.append(lab)

    for row in cleaned_es_laboratories:
        row['guidingKeywords'] = []

        # Get researchers from the laboratory
        rsr_param = esActions.scope_p("labHalId", row["halStructId"])

        if not es.indices.exists(index=row['structSirene'] + "-" + row["halStructId"] + "-researchers"):
            es.indices.create(index=row['structSirene'] + "-" + row["halStructId"] + "-researchers")

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
            es.index(index=row['structSirene'] + "-" + row["halStructId"] + "-laboratories",
                     id=row['halStructId'], body=json.dumps(row))
        else:
            docu = dict()  # from https://stackoverflow.com/questions/57564374/elasticsearch-update-gives-unknown-field-error
            docu["doc"] = row
            es.update(index=row['structSirene'] + "-" + row["halStructId"] + "-laboratories",
                      id=row['halStructId'], body=json.dumps(docu))

        # create laboratory document repertory
        if not es.indices.exists(index=row['structSirene'] + "-" + row["halStructId"] + "-laboratories-documents"):
            print(f"creating document directory for: {row['acronym']}(struct: {row['structSirene']})")
            es.indices.create(
                index=row['structSirene'] + "-" + row["halStructId"] + "-laboratories-documents")


def temp_laboratories(row):
    global Labolist
    row["validated"] = False
    row["halStructId"] = row["halStructId"].strip()
    if " " in row["halStructId"]:
        print(f"Please check {row['acronym']}({row['structSirene']}) in elastic, halStructId value is missing")
    else:
        connait_lab = row["halStructId"]
        if connait_lab not in Labolist:
            Labolist.append(connait_lab)


def create_index(structure, researcher, laboratories, csv_enabler=True, django_enabler=None):
    global csv_open, djangodb_open
    csv_open = csv_enabler
    djangodb_open = django_enabler
    print(time.strftime("%H:%M:%S", time.localtime()), end=' : ')
    print('Begin Index creation')
    print("\u2022", time.strftime("%H:%M:%S", time.localtime()), end=' : ')
    print('processing get_structid_list')
    get_structid_list()
    print("\u2022", time.strftime("%H:%M:%S", time.localtime()), end=' : ')
    print('processing get_labo_list')
    get_labo_list()

    print("\u2022", time.strftime("%H:%M:%S", time.localtime()), end=' : ')
    if structure:
        print('processing create_structures_index')
        create_structures_index()
    else:
        print('structure is disabled, skipping to next process')

    print("\u2022", time.strftime("%H:%M:%S", time.localtime()), end=' : ')
    if researcher:
        print('processing create_researchers_index')
        create_researchers_index()
    else:
        print('researcher is disabled, skipping to next process')

    print("\u2022", time.strftime("%H:%M:%S", time.localtime()), end=' : ')
    if laboratories:
        print('processing create_laboratories_index')
        create_laboratories_index()
    else:
        print('laboratories is disabled, skipping to next process')

    print(time.strftime("%H:%M:%S", time.localtime()), end=' : ')
    print('Index creation finished')


if __name__ == '__main__':
    create_index(structure='on', researcher='on', laboratories='on')