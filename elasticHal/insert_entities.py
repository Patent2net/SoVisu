import datetime
import json
import sys
import time

# Custom libs
from sovisuhal.libs import esActions
from elasticHal.libs import archivesOuvertes, utils, StructAcronym
# Celery
from celery import shared_task
# Celery-progress
from celery_progress.backend import ProgressRecorder

from elasticHal.models import Structure, Laboratory, Researcher

# Global variables declaration
structIdlist = []  # is dependant of get_structid_list()
Labolist = []

djangodb_open = None  # If djangodb_open = True script will use django Db to generate index for ES. Default Value is False vhen used as a script and True when called by SoVisu. (check the code at the bottom of the file)

init = True

# Connect to DB
es = esActions.es_connector()


# #print("__name__ value is : ", __name__)


def get_structid_list():
    """
    Récupère la liste des structures dans Elasticsearch et / ou Django DB afin de les stocker dans une variable globale
    """
    global structIdlist

    # get structId for already existing structures in ES
    scope_param = esActions.scope_all()
    count = es.count(index="*-structures", body=scope_param)['count']
    if count > 0:
        res = es.search(index="*-structures", body=scope_param, filter_path=["hits.hits._source.structSirene"])
        structIdlist = [hit['_source']['structSirene'] for hit in res['hits']['hits']]

    # get structId for structures in django db and compare with structIdlist
    if djangodb_open:
        for structure in Structure.objects.all():
            if structure.structSirene not in structIdlist:
                structIdlist.append(structure.structSirene)
            else:
                print("\u00A0 \u21D2 ", structure.acronym, " is already listed")


def get_labo_list():
    """
    Récupère la liste des laboratoires dans Elasticsearch et / ou Django DB afin de les stocker dans une variable globale
    """
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

    if djangodb_open:
        for row in Laboratory.objects.all().values():
            row.pop('id')
            temp_laboratories(row)


def create_structures_index(pg):
    """
    Crée les index de structures dans Elasticsearch
    """
    # Process structures

    if djangodb_open:
        percentage = 0.0
        for row in Structure.objects.all().values():
            row.pop('id')  # delete unique id added by django DB from the dict
            es.index(index=row["structSirene"] + "-structures", id=row['structSirene'], body=json.dumps(row))
            progress_description = "processing structure"
            percentage += 33 / len(Structure.objects.all().values())
            pg.set_progress(int(percentage), 100, description=progress_description)
    else:
        print("No source enabled to add structure. Please check the parameters")
    pg.set_progress(33, 100, description="processing structure finished")


def create_researchers_index(pg):
    """
    Crée les index de chercheurs dans Elasticsearch
    """
    # Process researchers
    scope_param = esActions.scope_all()
    percentage = 66.0
    progress_description = "processing researchers"
    pg.set_progress(int(percentage), 100, description=progress_description)
    cleaned_es_researchers = []
    for structid in structIdlist:
        count = es.count(index=structid + "*-researchers", body=scope_param)['count']
        res = es.search(index=structid + "*-researchers", body=scope_param, size=count)
        es_researchers = res['hits']['hits']
        for row in es_researchers:
            row = row['_source']
            cleaned_es_researchers.append(row)
    progress_description = "processing " + str(len(cleaned_es_researchers)) + " researchers"
    pg.set_progress(int(percentage), 100, description=progress_description)

    if djangodb_open:
        django_researchers = Researcher.objects.all().values()
        django_researchers = list([researcher for researcher in django_researchers if
                                   researcher['halId_s'] != '' and researcher.pop(
                                       'id')])  # Only keep researchers with known 'halId_s' and remove the 'id' value created by Django_DB
        if cleaned_es_researchers:
            for researcher in django_researchers:
                if any(dictlist['halId_s'] == researcher["halId_s"] for dictlist in cleaned_es_researchers):
                    print("\u00A0 \u21D2 ", researcher["halId_s"] + " is already in cleaned_es_researchers")
                else:
                    cleaned_es_researchers.append(researcher)
        else:
            cleaned_es_researchers = django_researchers
    cpt = 0
    docmap = {
        "properties": {
            "docid": {
                "type": "long"
            },
            "en_abstract_s": {
                "type": "text",  # formerly "string"
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 5000
                    }}
            },
            "fr_abstract_s": {
                "type": "text",  # formerly "string"
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 5000
                    }}
            },
            "it_abstract_s": {
                "type": "text",  # formerly "string"
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 5000
                    }}
            },
            "es_abstract_s": {
                "type": "text",  # formerly "string"
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 5000
                    }}
            },
            "pt_abstract_s": {
                "type": "text",  # formerly "string"
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 5000
                    }}
            }
        }
    }
    for row in cleaned_es_researchers:
        cpt += 1
        percentage = 66 + 33 * (cpt / len(cleaned_es_researchers))
        pg.set_progress(int(percentage), 100, description=progress_description)
        if row["structSirene"] in structIdlist:
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
                connait_lab = "non-labo"

            else:
                connait_lab = row["labHalId"]
                old_lab = row['labHalId']

            row['aurehalId'] = str(row['aurehalId']).strip()  # supprime les '\r' empêchant une erreur venant de SPARQL
            try:
                row['aurehalId'] = row['aurehalId'].replace(' --> En erreur, contactez-nous', '').strip()
                archives_ouvertes_data = archivesOuvertes.get_concepts_and_keywords(int(row['aurehalId']))
            except:
                archives_ouvertes_data = dict()
                archives_ouvertes_data['concepts'] = []
                row['aurehalId'] = str(row['aurehalId']) + " --> En erreur, contactez-nous"
                print("aille archives_ouvertes_data, ", row['aurehalId'])
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

                es.index(index=row['structSirene'] + "-" + connait_lab + "-researchers", id=row['ldapId'],
                         body=json.dumps(row))
            else:

                if not es.indices.exists(index=row["structSirene"] + "-" + connait_lab + "-researchers"):
                    es.indices.create(index=row["structSirene"] + "-" + connait_lab + "-researchers")
                    es.indices.create(index=row["structSirene"] + "-" + connait_lab + "-researchers-" + row[
                        "ldapId"] + "-documents")  # -researchers" + row["ldapId"] + "-documents
                    es.indices.put_mapping(
                        index=row["structSirene"] + "-" + connait_lab + "-researchers-" + row[
                            "ldapId"] + "-documents",
                        body=docmap,
                    )
                    es.index(index=row['structSirene'] + "-" + connait_lab + "-researchers", id=row['ldapId'],
                             body=json.dumps(row))
                elif not es.indices.exists(
                        index=row["structSirene"] + "-" + connait_lab + "-researchers-" + row["ldapId"] + "-documents"):
                    es.indices.create(index=row["structSirene"] + "-" + connait_lab + "-researchers-" + row[
                        "ldapId"] + "-documents")  # -researchers" + row["ldapId"] + "-documents" ?
                    es.indices.put_mapping(
                        index=row["structSirene"] + "-" + connait_lab + "-researchers-" + row["ldapId"] + "-documents",
                        body=docmap,
                    )
                else:
                    try:
                        docu = dict()  # from https://stackoverflow.com/questions/57564374/elasticsearch-update-gives-unknown-field-error
                        docu["doc"] = row  # MAIS : https://github.com/elastic/elasticsearch-py/issues/1698
                        es.update(index=row['structSirene'] + "-" + connait_lab + "-researchers", id=row['ldapId'],
                                  body=json.dumps(docu))
                    except:
                        try:
                            es.index(index=row['structSirene'] + "-" + connait_lab + "-researchers", id=row['ldapId'],
                                     body=json.dumps(row))
                        except:
                            print("boum 2 ???", connait_lab, row['ldapId'])
                if connait_lab != old_lab:
                    print(" détruire l'entrée ", row['structSirene'] + "-" + old_lab + "-researchers/" + row['ldapId'])

            if not es.indices.exists(
                    index=row["structSirene"] + "-" + connait_lab + "-researchers-" + row["ldapId"] + "-documents"):
                es.indices.create(
                    index=row["structSirene"] + "-" + connait_lab + "-researchers-" + row["ldapId"] + "-documents")
                es.indices.put_mapping(
                    index=row["structSirene"] + "-" + connait_lab + "-researchers-" + row["ldapId"] + "-documents",
                    body=docmap,
                    )

            if not es.indices.exists(index=row["structSirene"] + "-" + connait_lab + "-laboratories"):
                es.indices.create(index=row["structSirene"] + "-" + connait_lab + "-laboratories")

                es.indices.create(index=row["structSirene"] + "-" + connait_lab + "-laboratories-documents")
                es.indices.put_mapping(index=row["structSirene"] + "-" + connait_lab + "-laboratories-documents",
                                       body=docmap,
                                       )
            percentage += (33.0 / len(cleaned_es_researchers))
            progress_description = row["ldapId"] + " updated"
            pg.set_progress(int(percentage), 100, description=progress_description)
        else:
            #
            print('\u00A0 \u21D2 chercheur hors structure ', row['ldapId'], ", structure : ", row['structSirene'])


def create_laboratories_index(pg):
    """
    Créé les index pour les laboratoires
    """
    # Process laboratories
    scope_param = esActions.scope_all()
    percentage = 33
    progress_description = "Processing laboratories indexes"
    pg.set_progress(int(percentage), 100, description=progress_description)
    cleaned_es_laboratories = []
    for structid in structIdlist:
        count = es.count(index=structid + "*-laboratories", body=scope_param)['count']
        res = es.search(index=structid + "*-laboratories", body=scope_param, size=count)
        progress_description = 'processing create_laboratories_index'
        percentage = 66
        pg.set_progress(int(percentage), 100, description=progress_description)
        es_laboratories = res['hits']['hits']

        for row in es_laboratories:
            row = row['_source']
            cleaned_es_laboratories.append(row)

    if djangodb_open:
        if cleaned_es_laboratories:
            for lab in Laboratory.objects.all().values():
                lab.pop('id')
                if any(dictlist['halStructId'] == lab['halStructId'] for dictlist in cleaned_es_laboratories):
                    print(lab["acronym"] + " is already in cleaned_es_laboratories")

                else:
                    cleaned_es_laboratories.append(lab)

        else:
            for lab in Laboratory.objects.all().values():
                lab.pop('id')
                cleaned_es_laboratories.append(lab)

    for row in cleaned_es_laboratories:

        row['guidingKeywords'] = []

        # Get researchers from the laboratory
        rsr_param = esActions.scope_p("labHalId", row["halStructId"])

        if not es.indices.exists(index=row['structSirene'] + "-" + row["halStructId"] + "-researchers"):
            es.indices.create(index=row['structSirene'] + "-" + row["halStructId"] + "-researchers")

        es.indices.refresh(index=row['structSirene'] + "-" + row[
            "halStructId"] + "-researchers")  # force le refresh des indices(index) de elasticsearch
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
            docmap = {
                "properties": {
                    # "docid": {
                    #     "type": "long"
                    # },
                    "en_abstract_s": {
                        "type": "text",  # formerly "string"
                        "fields": {
                            "keyword": {
                                "type": "keyword",
                                "ignore_above": 1000
                            }}
                    },
                    "fr_abstract_s": {
                        "type": "text",  # formerly "string"
                        "fields": {
                            "keyword": {
                                "type": "keyword",
                                "ignore_above": 1000
                            }}
                    },
                    "it_abstract_s": {
                        "type": "text",  # formerly "string"
                        "fields": {
                            "keyword": {
                                "type": "keyword",
                                "ignore_above": 1000
                            }}
                    },
                    "es_abstract_s": {
                        "type": "text",  # formerly "string"
                        "fields": {
                            "keyword": {
                                "type": "keyword",
                                "ignore_above": 1000
                            }}
                    },
                    "pt_abstract_s": {
                        "type": "text",  # formerly "string"
                        "fields": {
                            "keyword": {
                                "type": "keyword",
                                "ignore_above": 1000
                            }}
                    }
                }
            }

            es.indices.create(index=row['structSirene'] + "-" + row["halStructId"] + "-laboratories-documents")
            es.indices.put_mapping(index=row['structSirene'] + "-" + row["halStructId"] + "-laboratories-documents",
                                   body=docmap,
                                   )
        percentage += (33.0 / len(cleaned_es_laboratories))
        progress_description = row["acronym"] + " updated"
        pg.set_progress(int(percentage), 100, description=progress_description)
    pg.set_progress(100, 100, description="finished")
    StructAcronym.return_struct()
    return "finished"


def temp_laboratories(row):
    """
    Nettoie les données provenant de Django avant de les comparer à celles d'Elastic pour insérer les données manquantes.
    """
    global Labolist
    row["validated"] = False
    row["halStructId"] = row["halStructId"].strip()
    if " " in row["halStructId"]:
        print(f"Please check {row['acronym']}({row['structSirene']}) in elastic, halStructId value is missing")
    else:
        connait_lab = row["halStructId"]
        if connait_lab not in Labolist:
            Labolist.append(connait_lab)


@shared_task(bind=True)
def create_index(self, structure, researcher, laboratories, django_enabler=None):
    """
    Initialise la création d'un index pour les catégories sélectionnées (structure, researcher, laboratories)
    """
    global djangodb_open
    progress_recorder = ProgressRecorder(self)
    djangodb_open = django_enabler
    get_structid_list()
    get_labo_list()
    percentage = 0
    if structure:
        progress_description = 'processing create_structures_index'
        percentage = 33
        progress_recorder.set_progress(int(percentage), 100, description=progress_description)
        create_structures_index(progress_recorder)
    else:
        progress_recorder.set_progress(int(percentage), 100,
                                       description='structure is disabled, skipping to next process')

    if laboratories:

        progress_description = 'processing create_laboratories_index'
        create_laboratories_index(progress_recorder)
        percentage = 66
        progress_recorder.set_progress(int(percentage), 100, description=progress_description)
    else:
        progress_recorder.set_progress(int(percentage), 100,
                                       description='laboratories is disabled, skipping to next process')

    if researcher:

        progress_description = 'processing create_researchers_index'
        create_researchers_index(progress_recorder)
        percentage = 99
        progress_recorder.set_progress(int(percentage), 100, description=progress_description)
    else:
        progress_recorder.set_progress(int(percentage), 100,
                                       description='researcher is disabled, skipping to next process')

    progress_description = 'Index creation finished'
    percentage = 100
    progress_recorder.set_progress(int(percentage), 100, description=progress_description)
    return "finished"
