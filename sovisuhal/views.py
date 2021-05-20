from django.shortcuts import render, redirect
from elasticsearch import Elasticsearch, helpers
from datetime import datetime
import json
from . import forms
from django.views.decorators.clickjacking import xframe_options_exempt

from django.core.mail import mail_admins, send_mail
from .forms import ContactForm
from decouple import config
from django.contrib import messages
#from ssl import create_default_context
#from elasticsearch.connection import create_ssl_context
from uniauth.decorators import login_required

try:
    mode = config("mode")  # Prod --> mode = 'Prod' en env Var
except:
    mode = "Dev"
try:
    structId = config("structId")
except:
    structId = "198307662"  # UTLN

#struct = "198307662"

def esConnector(mode = mode):
    if mode == "Prod":

        secret = config ('ELASTIC_PASSWORD')
        # context = create_ssl_context(cafile="../../stackELK/secrets/certs/ca/ca.crt")
        es = Elasticsearch('localhost',
                           http_auth=('elastic', secret),
                           scheme="http",
                           port=9200,
                           # ssl_context=context,
                           timeout=10)
    else:
        es = Elasticsearch([{'host': 'localhost', 'port': 9200}])
    return es

@login_required
def index(request):
    if not request.user.is_authenticated:
        return redirect('%s?next=%s' % (settings.LOGIN_URL, request.path))
    else:
        gugusse = request.user.get_username()

        gugusse = gugusse.replace('cas-utln-', '')

        return redirect('check/?type=rsr&id=' + gugusse +'&from=1990-01-01&to=2021-05-20')


@login_required
def unknown(request):
    return redirect('/accounts/login/')
    #return render(request, '404.html')

def help(request):
    return render(request, 'help.html')

# Pages

def cs_index(request):
    # Get parameters
    if 'type' in request.GET:
        type = request.GET['type']

    if 'id' in request.GET:
        id = request.GET['id']
    else:
        id = -1
    # /

    # Connect to DB
    es = esConnector()

    if type == "lab":
        scope_param = {
            "query": {
                "match_all": {}
            }
        }

        count = es.count(index=structId +"*-laboratories", body=scope_param)['count']
        res = es.search(index= structId + "*-laboratories", body=scope_param, size=count)
        entities = res['hits']['hits']

    elif type == "rsr":

        if id == -1:
            scope_param = {
                "query": {
                    "match_all": {}
                }
            }

            count = es.count(index=structId +"*-researchers", body=scope_param)['count']
            res = es.search(index=structId + "*-researchers", body=scope_param, size=count)
        else:
            scope_param = {
                "query": {
                    "match": {
                        "labHalId": id
                    }
                }
            }

            count = es.count(index=structId +"-" + id  +"-researchers", body=scope_param)['count']

            res = es.search(index=structId +"-" + id +"-researchers", body=scope_param, size=count)
        entities = res['hits']['hits']

    cleaned_entities = []

    for entity in entities:
        cleaned_entities.append(entity['_source'])

    # /

    return render(request, 'index.html', {'entities': cleaned_entities, 'type': type})

def dashboard(request):
    # Get parameters
    if 'type' in request.GET:
        type = request.GET['type']
    else:
        return redirect('unknown')
    if 'id' in request.GET:
        id = request.GET['id']
    else:
        return redirect('unknown')
    # /

    # Connect to DB
    es = esConnector()

    # Get scope informations
    if type == "rsr":
        scope_param = {
            "query": {
                "match": {
                    "_id": id
                }
            }
        }

        key = 'halId_s'
        ext_key = "harvested_from_ids"

        res = es.search(index=structId +"*-researchers", body=scope_param) # on pointe sur index générique car pas de LabHalId

        entity = res['hits']['hits'][0]['_source']

    elif type == "lab":
        scope_param = {
            "query": {
                "match": {
                    "halStructId": id
                }
            }
        }

        key = "halStructId"
        ext_key = "harvested_from_ids"

        res = es.search(index=structId +"-"+ id  +"-laboratories", body=scope_param)
        entity = res['hits']['hits'][0]['_source']
    # /

    hasToConfirm = False

    if type == "rsr":
        hasToConfirm_param = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "match_phrase": {
                                "authIdHal_s": entity['halId_s']
                            }
                        },
                        {
                            "match": {
                                "validated": False
                            }
                        }
                    ]
                }
            }
        }
        # devrait scindé en deux ex.count qui diffèrent selon lab ou rsr dans les if précédent
        #  par ex pour == if type == "rsr": : es.count(index=struct  + "-" + entity['halStructId']+"-"researchers-" + entity["ldapId"] +"-documents", body=hasToConfirm_param)['count'] > 0:

    if type == "lab":
        hasToConfirm_param = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "match_phrase": {
                                "labStructId_i": entity['halStructId']
                            }
                        },
                        {
                            "match": {
                                "validated": False
                            }
                        }
                    ]
                }
            }
        }

    if es.count(index=structId  + "*-documents", body=hasToConfirm_param)['count'] > 0: # devrait scindé en deux ex.count qui diffèrent selon lab ou rsr dans les if précédent
                                                                                    #  par ex pour == if type == "lab": : es.count(index=struct  + "-" + entity['halStructId']+"-documents", body=hasToConfirm_param)['count'] > 0:
        hasToConfirm = True

    # Get first submittedDate_tdate date
    if type == "rsr":
        start_date_param = {
            "size": 1,
            "sort": [
                {"submittedDate_tdate": {"order": "asc"}}
            ],
            "query": {
                "match_phrase": {"harvested_from_ids": entity['halId_s']}
            }
        }
        res = es.search(index=structId +"*-documents", body=start_date_param)
    elif type == "lab":
        start_date_param = {
            "size": 1,
            "sort": [
                {"submittedDate_tdate": {"order": "asc"}}
            ],
            "query": {
                "match_phrase": {"harvested_from_ids": entity['halStructId']}
            }
        }
        res = es.search(index=structId + "*-documents", body=start_date_param)
        # peut-on pointer sur index plus précis

    start_date = res['hits']['hits'][0]['_source']['submittedDate_tdate']
    # /

    # Get parameters
    if 'from' in request.GET:
        dateFrom = request.GET['from']
    else:
        dateFrom = start_date[0:4] + '-01-01'

    if 'to' in request.GET:
        dateTo = request.GET['to']
    else:
        dateTo = datetime.today().strftime('%Y-%m-%d')
    # /

    return render(request, 'dashboard.html', {'type': type, 'id': id, 'from': dateFrom, 'to': dateTo,
                                              'entity': entity,
                                              'hasToConfirm': hasToConfirm,
                                              'filter': ext_key + ':"' + entity[key] + '" AND validated:true',
                                              'startDate': start_date,
                                              'timeRange': "from:'" + dateFrom + "',to:'" + dateTo + "'"})


def references(request):
    # Get parameters
    if 'type' in request.GET:
        type = request.GET['type']
    else:
        return redirect('unknown')
    if 'id' in request.GET:
        id = request.GET['id']
    else:
        return redirect('unknown')
    if 'filter' in request.GET:
        filter = request.GET['filter']
    else:
        filter = -1
    # /

    # Connect to DB
    es = esConnector()

    # Get scope informations
    if type == "rsr":
        scope_param = {
            "query": {
                "match": {
                    "_id": id
                }
            }
        }

        key = 'halId_s'
        ext_key = "harvested_from_ids"

        res = es.search(index= structId  +"-*-researchers", body=scope_param)
        entity = res['hits']['hits'][0]['_source']

    elif type == "lab":
        scope_param = {
            "query": {
                "match": {
                    "halStructId": id
                }
            }
        }

        key = "halStructId"
        ext_key = "harvested_from_ids"

        res = es.search(index= structId  +"-" + id + "-laboratories", body=scope_param)
        entity = res['hits']['hits'][0]['_source']
    # /

    # Get first submittedDate_tdate date
    if type == "rsr":
        start_date_param = {
            "size": 1,
            "sort": [
                {"submittedDate_tdate": {"order": "asc"}}
            ],
            "query": {
                "match_phrase": {"harvested_from_ids": entity['halId_s']}
            }
        }
        res = es.search(index=structId + "-" + entity['labHalId'] + "-researchers-"+entity['ldapId']+"-documents", body=start_date_param) # labHalId est-il là ?
    elif type == "lab":
        start_date_param = {
            "size": 1,
            "sort": [
                {"submittedDate_tdate": {"order": "asc"}}
            ],
            "query": {
                "match_phrase": {"harvested_from_ids": entity['halStructId']}
            }
        }
        res = es.search(index=structId + "-" + id + "-laboratories-documents", body=start_date_param)

    start_date = res['hits']['hits'][0]['_source']['submittedDate_tdate']
    # /

    # Get parameters
    if 'from' in request.GET:
        dateFrom = request.GET['from']
    else:
        dateFrom = start_date[0:4] + '-01-01'

    if 'to' in request.GET:
        dateTo = request.GET['to']
    else:
        dateTo = datetime.today().strftime('%Y-%m-%d')
    # /

    hasToConfirm = False

    if type == "rsr":
        hasToConfirm_param = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "match_phrase": {
                                "harvested_from_ids": entity['halId_s']
                            }
                        },
                        {
                            "match": {
                                "validated": False
                            }
                        }
                    ]
                }
            }
        }
        if es.count(index=structId + "-" + entity['labHalId'] + "-researchers-"+entity['ldapId']+"-documents", body=hasToConfirm_param)['count'] > 0:
            hasToConfirm = True
    if type == "lab":
        hasToConfirm_param = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "match_phrase": {
                                "harvested_from_ids": entity['halStructId']
                            }
                        },
                        {
                            "match": {
                                "validated": False
                            }
                        }
                    ]
                }
            }
        }

        if es.count(index=structId + "-" + entity['halStructId'] + "-laboratories-documents", body=hasToConfirm_param)['count'] > 0:
            hasToConfirm = True

    # Get references
    ref_param = {
        "query": {
            "bool": {
                "filter": [
                    {
                        "match_phrase": {
                            ext_key: entity[key]
                        }
                    },
                    {
                        "match": {
                            "validated": True
                        }
                    },
                    {
                        "range": {
                            "submittedDate_tdate": {
                                "gte": dateFrom,
                                "lt": dateTo
                            }
                        }
                    }
                ]
            }
        }
    }

    if filter == "uncomplete":
        ref_param = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "bool": {
                                "must": [
                                    {
                                        "match_phrase": {
                                            "validated": True,
                                        }
                                    },
                                    {
                                        "match_phrase": {
                                            ext_key: entity[key],
                                        }
                                    },
                                    {
                                        "range": {
                                            "submittedDate_tdate": {
                                                "gte": dateFrom,
                                                "lt": dateTo
                                            }
                                        }
                                    },
                                ]
                            }
                        },
                        {
                            "bool": {
                                "should": [
                                    {
                                        "bool": {
                                            "must_not": [
                                                {
                                                    "exists": {
                                                        "field": "fileMain_s"
                                                    }
                                                }
                                            ]
                                        }
                                    },
                                    {
                                        "bool": {
                                            "must_not": [
                                                {
                                                    "exists": {
                                                        "field": "*_abstract_s"
                                                    }
                                                }
                                            ]
                                        }
                                    }
                                ]
                            }
                        }
                    ]
                }
            }
        }

    if filter == "complete":
        ref_param = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "bool": {
                                "must": [
                                    {
                                        "match_phrase": {
                                            "validated": True,
                                        }
                                    },
                                    {
                                        "match_phrase": {
                                            ext_key: entity[key]
                                        }
                                    },
                                    {
                                        "range": {
                                            "submittedDate_tdate": {
                                                "gte": dateFrom,
                                                "lt": dateTo
                                            }
                                        }
                                    },
                                ]
                            }
                        },
                        {
                            "bool": {
                                "must": [
                                    {
                                        "exists": {
                                            "field": "fileMain_s"
                                        }
                                    },
                                    {
                                        "exists": {
                                            "field": "*_abstract_s"
                                        }
                                    }
                                ]
                            }
                        }
                    ]
                }
            }
        }

    if type == "rsr":  # I hope this is a focused search :-/
        count = es.count(index=structId + "-" + entity ["labHalId"] + "-researchers-"+entity['ldapId']+"-documents", body=ref_param)['count']
        references = es.search(index=structId + "-" + entity ["labHalId"] + "-researchers-"+entity['ldapId']+"-documents", body=ref_param, size=count)

    if type == "lab":
        count = es.count(index=structId + "-" + entity ["halStructId"] + "-laboratories-documents", body=ref_param)['count']
        references = es.search(index=structId + "-" + entity ["halStructId"] + "-laboratories-documents", body=ref_param, size=count)

    references_cleaned = []

    for ref in references['hits']['hits']:
        references_cleaned.append(ref['_source'])
    # /

    return render(request, 'references.html', {'filter': filter, 'type': type, 'id': id, 'from': dateFrom, 'to': dateTo,
                                               'entity': entity,
                                               'hasToConfirm': hasToConfirm,
                                               'references': references_cleaned, 'startDate': start_date,
                                               'timeRange': "from:'" + dateFrom + "',to:'" + dateTo + "'"})


def check(request):
    # Connect to DB
    es = esConnector()

    # Get parameters
    if 'type' in request.GET:
        type = request.GET['type']
    else:
        return redirect('unknown')
    if 'id' in request.GET:
        id = request.GET['id']
    else:
        return redirect('unknown')
    if 'data' in request.GET:
        data = request.GET['data']
    else:
        data = -1

    # /

    # Get scope informations
    if type == "rsr":
        scope_param = {
            "query": {
                "match": {
                    "_id": id
                }
            }
        }

        key = 'halId_s'
        ext_key = "harvested_from_ids"

        res = es.search(index= structId  + "-*-researchers*", body=scope_param)
        entity = res['hits']['hits'][0]['_source']

    elif type == "lab":
        scope_param = {
            "query": {
                "match": {
                    "halStructId": id
                }
            }
        }

        key = "halStructId"
        ext_key = "harvested_from_ids"

        res = es.search(index= structId  +"-*-laboratories", body=scope_param)
        entity = res['hits']['hits'][0]['_source']
    # /

    # Get first submittedDate_tdate date
    if type == "rsr":
        start_date_param = {
            "size": 1,
            "sort": [
                {"submittedDate_tdate": {"order": "asc"}}
            ],
            "query": {
                "match_phrase": {"harvested_from_ids": entity['halId_s']}
            }
        }
        res = es.search(index=structId + "-"+entity['labHalId']+"-researchers-" + id + "-documents", body=start_date_param)
    elif type == "lab":
        start_date_param = {
            "size": 1,
            "sort": [
                {"submittedDate_tdate": {"order": "asc"}}
            ],
            "query": {
                "match_phrase": {"harvested_from_ids": entity['halStructId']}
            }
        }
        res = es.search(index=structId + "-" + entity['halStructId']+"-laboratories-documents", body=start_date_param)


    start_date = res['hits']['hits'][0]['_source']['submittedDate_tdate']
    # /

    # Get parameters
    if 'from' in request.GET:
        dateFrom = request.GET['from']
    else:
        dateFrom = start_date[0:4] + '-01-01'

    if 'to' in request.GET:
        dateTo = request.GET['to']
    else:
        dateTo = datetime.today().strftime('%Y-%m-%d')
    # /

    if data == "state":
        rsr_param = {
            "query": {
                "match": {
                    "labHalId": id
                }
            }
        }
        count = es.count(index=structId  +"*-researchers", body=rsr_param)['count']

        rsrs = es.search(index= structId  +"-*-researchers", body=rsr_param, size=count)

        rsrs_cleaned = []

        for result in rsrs['hits']['hits']:
            rsrs_cleaned.append(result['_source'])

        return render(request, 'check.html', {'data': data, 'type': type, 'id': id, 'from': dateFrom, 'to': dateTo,
                                              'entity': entity,
                                              'researchers': rsrs_cleaned,
                                              'startDate': start_date,
                                              'timeRange': "from:'" + dateFrom + "',to:'" + dateTo + "'"})

    if data == "-1" or data == "credentials":

        if type == "rsr":
            orcId = ''
            if 'orcId' in entity:
                orcId = entity['orcId']

            return render(request, 'check.html', {'data': data, 'type': type, 'id': id, 'from': dateFrom, 'to': dateTo,
                                                  'entity': entity, 'extIds': ['a','b','c'],
                                                  'form': forms.validCredentials(halId_s=entity['halId_s'],
                                                                                 idRef=entity['idRef'], orcId=orcId),
                                                  'startDate': start_date,
                                                  'timeRange': "from:'" + dateFrom + "',to:'" + dateTo + "'"})

        if type == "lab":
            return render(request, 'check.html', {'data': data, 'type': type, 'id': id, 'from': dateFrom, 'to': dateTo,
                                                  'entity': entity,
                                                  'form': forms.validLabCredentials(halStructId=entity['halStructId'],
                                                                                    rsnr=entity['rsnr'],
                                                                                    idRef=entity['idRef']),
                                                  'startDate': start_date,
                                                  'timeRange': "from:'" + dateFrom + "',to:'" + dateTo + "'"})

    elif data == "expertise":

        concepts = []
        if 'children' in entity['concepts']:
            for children in entity['concepts']['children']:
                if 'state' not in children:
                    concepts.append({'id': children['id'], 'label_fr': children['label_fr']})
                if 'children' in children:
                    for children1 in children['children']:
                        if 'state' not in children1:
                            concepts.append({'id': children1['id'], 'label_fr': children1['label_fr']})
                        if 'children' in children1:
                            for children2 in children1['children']:
                                if 'state' not in children2:
                                    concepts.append({'id': children2['id'], 'label_fr': children2['label_fr']})

        return render(request, 'check.html', {'data': data, 'type': type, 'id': id, 'from': dateFrom, 'to': dateTo,
                                              'entity': entity,
                                              'concepts': concepts,
                                              'startDate': start_date,
                                              'timeRange': "from:'" + dateFrom + "',to:'" + dateTo + "'"})

    elif data == "guiding-keywords":
        return render(request, 'check.html', {'data': data, 'type': type, 'id': id, 'from': dateFrom, 'to': dateTo,
                                              'entity': entity,
                                              'form': forms.setGuidingKeywords(
                                                  guidingKeywords=entity['guidingKeywords']),
                                              'startDate': start_date,
                                              'timeRange': "from:'" + dateFrom + "',to:'" + dateTo + "'"})

    elif data == "guiding-domains":

        domains = {'id': 'Concepts', 'children': [{'id': 'chim', 'label_en': 'Chemical Sciences', 'label_fr': 'Chimie', 'children': [{'id': 'chim.anal', 'label_en': 'Analytical chemistry', 'label_fr': 'Chimie analytique', 'children': []}, {'id': 'chim.cata', 'label_en': 'Catalysis', 'label_fr': 'Catalyse', 'children': []}, {'id': 'chim.chem', 'label_en': 'Cheminformatics', 'label_fr': 'Chemo-informatique', 'children': []}, {'id': 'chim.coor', 'label_en': 'Coordination chemistry', 'label_fr': 'Chimie de coordination', 'children': []}, {'id': 'chim.cris', 'label_en': 'Cristallography', 'label_fr': 'Cristallographie', 'children': []}, {'id': 'chim.geni', 'label_en': 'Chemical engineering', 'label_fr': 'Génie chimique', 'children': []}, {'id': 'chim.inor', 'label_en': 'Inorganic chemistry', 'label_fr': 'Chimie inorganique', 'children': []}, {'id': 'chim.mate', 'label_en': 'Material chemistry', 'label_fr': 'Matériaux', 'children': []}, {'id': 'chim.orga', 'label_en': 'Organic chemistry', 'label_fr': 'Chimie organique', 'children': []}, {'id': 'chim.othe', 'label_en': 'Other', 'label_fr': 'Autre', 'children': []}, {'id': 'chim.poly', 'label_en': 'Polymers', 'label_fr': 'Polymères', 'children': []}, {'id': 'chim.radio', 'label_en': 'Radiochemistry', 'label_fr': 'Radiochimie', 'children': []}, {'id': 'chim.theo', 'label_en': 'Theoretical and/or physical chemistry', 'label_fr': 'Chimie théorique et/ou physique', 'children': []}, {'id': 'chim.ther', 'label_en': 'Medicinal Chemistry', 'label_fr': 'Chimie thérapeutique', 'children': []}]}, {'id': 'info', 'label_en': 'Computer Science', 'label_fr': 'Informatique', 'children': [{'id': 'info.eiah', 'label_en': 'Technology for Human Learning', 'label_fr': "Environnements Informatiques pour l'Apprentissage Humain", 'children': []}, {'id': 'info.info-ai', 'label_en': 'Artificial Intelligence', 'label_fr': 'Intelligence artificielle', 'children': []}, {'id': 'info.info-ao', 'label_en': 'Computer Arithmetic', 'label_fr': 'Arithmétique des ordinateurs', 'children': []}, {'id': 'info.info-ar', 'label_en': 'Hardware Architecture', 'label_fr': 'Architectures Matérielles', 'children': []}, {'id': 'info.info-au', 'label_en': 'Automatic Control Engineering', 'label_fr': 'Automatique', 'children': []}, {'id': 'info.info-bi', 'label_en': 'Bioinformatics', 'label_fr': 'Bio-informatique', 'children': []}, {'id': 'info.info-bt', 'label_en': 'Biotechnology', 'label_fr': 'Biotechnologie', 'children': []}, {'id': 'info.info-cc', 'label_en': 'Computational Complexity', 'label_fr': 'Complexité', 'children': []}, {'id': 'info.info-ce', 'label_en': 'Computational Engineering, Finance, and Science', 'label_fr': 'Ingénierie, finance et science', 'children': []}, {'id': 'info.info-cg', 'label_en': 'Computational Geometry', 'label_fr': 'Géométrie algorithmique', 'children': []}, {'id': 'info.info-cl', 'label_en': 'Computation and Language', 'label_fr': 'Informatique et langage', 'children': []}, {'id': 'info.info-cr', 'label_en': 'Cryptography and Security', 'label_fr': 'Cryptographie et sécurité', 'children': []}, {'id': 'info.info-cv', 'label_en': 'Computer Vision and Pattern Recognition', 'label_fr': 'Vision par ordinateur et reconnaissance de formes', 'children': []}, {'id': 'info.info-cy', 'label_en': 'Computers and Society', 'label_fr': 'Ordinateur et société', 'children': []}, {'id': 'info.info-db', 'label_en': 'Databases', 'label_fr': 'Base de données', 'children': []}, {'id': 'info.info-dc', 'label_en': 'Distributed, Parallel, and Cluster Computing', 'label_fr': 'Calcul parallèle, distribué et partagé', 'children': []}, {'id': 'info.info-dl', 'label_en': 'Digital Libraries', 'label_fr': 'Bibliothèque électronique', 'children': []}, {'id': 'info.info-dm', 'label_en': 'Discrete Mathematics', 'label_fr': 'Mathématique discrète', 'children': []}, {'id': 'info.info-ds', 'label_en': 'Data Structures and Algorithms', 'label_fr': 'Algorithme et structure de données', 'children': []}, {'id': 'info.info-es', 'label_en': 'Embedded Systems', 'label_fr': 'Systèmes embarqués', 'children': []}, {'id': 'info.info-gl', 'label_en': 'General Literature', 'label_fr': 'Littérature générale', 'children': []}, {'id': 'info.info-gr', 'label_en': 'Graphics', 'label_fr': "Synthèse d'image et réalité virtuelle", 'children': []}, {'id': 'info.info-gt', 'label_en': 'Computer Science and Game Theory', 'label_fr': 'Informatique et théorie des jeux', 'children': []}, {'id': 'info.info-hc', 'label_en': 'Human-Computer Interaction', 'label_fr': 'Interface homme-machine', 'children': []}, {'id': 'info.info-ia', 'label_en': 'Computer Aided Engineering', 'label_fr': 'Ingénierie assistée par ordinateur', 'children': []}, {'id': 'info.info-im', 'label_en': 'Medical Imaging', 'label_fr': 'Imagerie médicale', 'children': []}, {'id': 'info.info-ir', 'label_en': 'Information Retrieval', 'label_fr': "Recherche d'information", 'children': []}, {'id': 'info.info-it', 'label_en': 'Information Theory', 'label_fr': "Théorie de l'information", 'children': []}, {'id': 'info.info-iu', 'label_en': 'Ubiquitous Computing', 'label_fr': 'Informatique ubiquitaire', 'children': []}, {'id': 'info.info-lg', 'label_en': 'Machine Learning', 'label_fr': 'Apprentissage', 'children': []}, {'id': 'info.info-lo', 'label_en': 'Logic in Computer Science', 'label_fr': 'Logique en informatique', 'children': []}, {'id': 'info.info-ma', 'label_en': 'Multiagent Systems', 'label_fr': 'Système multi-agents', 'children': []}, {'id': 'info.info-mc', 'label_en': 'Mobile Computing', 'label_fr': 'Informatique mobile', 'children': []}, {'id': 'info.info-mm', 'label_en': 'Multimedia', 'label_fr': 'Multimédia', 'children': []}, {'id': 'info.info-mo', 'label_en': 'Modeling and Simulation', 'label_fr': 'Modélisation et simulation', 'children': []}, {'id': 'info.info-ms', 'label_en': 'Mathematical Software', 'label_fr': 'Logiciel mathématique', 'children': []}, {'id': 'info.info-na', 'label_en': 'Numerical Analysis', 'label_fr': 'Analyse numérique', 'children': []}, {'id': 'info.info-ne', 'label_en': 'Neural and Evolutionary Computing', 'label_fr': 'Réseau de neurones', 'children': []}, {'id': 'info.info-ni', 'label_en': 'Networking and Internet Architecture', 'label_fr': 'Réseaux et télécommunications', 'children': []}, {'id': 'info.info-oh', 'label_en': 'Other', 'label_fr': 'Autre', 'children': []}, {'id': 'info.info-os', 'label_en': 'Operating Systems', 'label_fr': "Système d'exploitation", 'children': []}, {'id': 'info.info-pf', 'label_en': 'Performance', 'label_fr': 'Performance et fiabilité', 'children': []}, {'id': 'info.info-et', 'label_en': 'Emerging Technologies', 'label_fr': 'Technologies Émergeantes', 'children': []}, {'id': 'info.info-pl', 'label_en': 'Programming Languages', 'label_fr': 'Langage de programmation', 'children': []}, {'id': 'info.info-rb', 'label_en': 'Robotics', 'label_fr': 'Robotique', 'children': []}, {'id': 'info.info-ro', 'label_en': 'Operations Research', 'label_fr': 'Recherche opérationnelle', 'children': []}, {'id': 'info.info-sc', 'label_en': 'Symbolic Computation', 'label_fr': 'Calcul formel', 'children': []}, {'id': 'info.info-sd', 'label_en': 'Sound', 'label_fr': 'Son', 'children': []}, {'id': 'info.info-se', 'label_en': 'Software Engineering', 'label_fr': 'Génie logiciel', 'children': []}, {'id': 'info.info-ti', 'label_en': 'Image Processing', 'label_fr': 'Traitement des images', 'children': []}, {'id': 'info.info-ts', 'label_en': 'Signal and Image Processing', 'label_fr': "Traitement du signal et de l'image", 'children': []}, {'id': 'info.info-tt', 'label_en': 'Document and Text Processing', 'label_fr': 'Traitement du texte et du document', 'children': []}, {'id': 'info.info-wb', 'label_en': 'Web', 'label_fr': 'Web', 'children': []}, {'id': 'info.info-fl', 'label_en': 'Formal Languages and Automata Theory', 'label_fr': 'Théorie et langage formel', 'children': []}, {'id': 'info.info-si', 'label_en': 'Social and Information Networks', 'label_fr': "Réseaux sociaux et d'information", 'children': []}, {'id': 'info.info-sy', 'label_en': 'Systems and Control', 'label_fr': 'Systèmes et contrôle', 'children': []}]}, {'id': 'math', 'label_en': 'Mathematics', 'label_fr': 'Mathématiques', 'children': [{'id': 'math.math-ac', 'label_en': 'Commutative Algebra', 'label_fr': 'Algèbre commutative', 'children': []}, {'id': 'math.math-ag', 'label_en': 'Algebraic Geometry', 'label_fr': 'Géométrie algébrique', 'children': []}, {'id': 'math.math-ap', 'label_en': 'Analysis of PDEs', 'label_fr': 'Equations aux dérivées partielles', 'children': []}, {'id': 'math.math-at', 'label_en': 'Algebraic Topology', 'label_fr': 'Topologie algébrique', 'children': []}, {'id': 'math.math-ca', 'label_en': 'Classical Analysis and ODEs', 'label_fr': 'Analyse classique', 'children': []}, {'id': 'math.math-co', 'label_en': 'Combinatorics', 'label_fr': 'Combinatoire', 'children': []}, {'id': 'math.math-ct', 'label_en': 'Category Theory', 'label_fr': 'Catégories et ensembles', 'children': []}, {'id': 'math.math-cv', 'label_en': 'Complex Variables', 'label_fr': 'Variables complexes', 'children': []}, {'id': 'math.math-dg', 'label_en': 'Differential Geometry', 'label_fr': 'Géométrie différentielle', 'children': []}, {'id': 'math.math-ds', 'label_en': 'Dynamical Systems', 'label_fr': 'Systèmes dynamiques', 'children': []}, {'id': 'math.math-fa', 'label_en': 'Functional Analysis', 'label_fr': 'Analyse fonctionnelle', 'children': []}, {'id': 'math.math-gm', 'label_en': 'General Mathematics', 'label_fr': 'Mathématiques générales', 'children': []}, {'id': 'math.math-gn', 'label_en': 'General Topology', 'label_fr': 'Topologie générale', 'children': []}, {'id': 'math.math-gr', 'label_en': 'Group Theory', 'label_fr': 'Théorie des groupes', 'children': []}, {'id': 'math.math-gt', 'label_en': 'Geometric Topology', 'label_fr': 'Topologie géométrique', 'children': []}, {'id': 'math.math-ho', 'label_en': 'History and Overview', 'label_fr': 'Histoire et perspectives sur les mathématiques', 'children': []}, {'id': 'math.math-it', 'label_en': 'Information Theory', 'label_fr': "Théorie de l'information et codage", 'children': []}, {'id': 'math.math-kt', 'label_en': 'K-Theory and Homology', 'label_fr': 'K-théorie et homologie', 'children': []}, {'id': 'math.math-lo', 'label_en': 'Logic', 'label_fr': 'Logique', 'children': []}, {'id': 'math.math-mg', 'label_en': 'Metric Geometry', 'label_fr': 'Géométrie métrique', 'children': []}, {'id': 'math.math-mp', 'label_en': 'Mathematical Physics', 'label_fr': 'Physique mathématique', 'children': []}, {'id': 'math.math-na', 'label_en': 'Numerical Analysis', 'label_fr': 'Analyse numérique', 'children': []}, {'id': 'math.math-nt', 'label_en': 'Number Theory', 'label_fr': 'Théorie des nombres', 'children': []}, {'id': 'math.math-oa', 'label_en': 'Operator Algebras', 'label_fr': "Algèbres d'opérateurs", 'children': []}, {'id': 'math.math-oc', 'label_en': 'Optimization and Control', 'label_fr': 'Optimisation et contrôle', 'children': []}, {'id': 'math.math-pr', 'label_en': 'Probability', 'label_fr': 'Probabilités', 'children': []}, {'id': 'math.math-qa', 'label_en': 'Quantum Algebra', 'label_fr': 'Algèbres quantiques', 'children': []}, {'id': 'math.math-ra', 'label_en': 'Rings and Algebras', 'label_fr': 'Anneaux et algèbres', 'children': []}, {'id': 'math.math-rt', 'label_en': 'Representation Theory', 'label_fr': 'Théorie des représentations', 'children': []}, {'id': 'math.math-sg', 'label_en': 'Symplectic Geometry', 'label_fr': 'Géométrie symplectique', 'children': []}, {'id': 'math.math-sp', 'label_en': 'Spectral Theory', 'label_fr': 'Théorie spectrale', 'children': []}, {'id': 'math.math-st', 'label_en': 'Statistics', 'label_fr': 'Statistiques', 'children': []}]}, {'id': 'nlin', 'label_en': 'Nonlinear Sciences', 'label_fr': 'Science non linéaire', 'children': [{'id': 'nlin.nlin-ao', 'label_en': 'Adaptation and Self-Organizing Systems', 'label_fr': 'Adaptation et Systèmes auto-organisés', 'children': []}, {'id': 'nlin.nlin-cd', 'label_en': 'Chaotic Dynamics', 'label_fr': 'Dynamique Chaotique', 'children': []}, {'id': 'nlin.nlin-cg', 'label_en': 'Cellular Automata and Lattice Gases', 'label_fr': 'Automates cellulaires et gaz sur réseau', 'children': []}, {'id': 'nlin.nlin-ps', 'label_en': 'Pattern Formation and Solitons', 'label_fr': 'Formation de Structures et Solitons', 'children': []}, {'id': 'nlin.nlin-si', 'label_en': 'Exactly Solvable and Integrable Systems', 'label_fr': 'Systèmes Solubles et Intégrables', 'children': []}]}, {'id': 'phys', 'label_en': 'Physics', 'label_fr': 'Physique', 'children': [{'id': 'phys.astr', 'label_en': 'Astrophysics', 'label_fr': 'Astrophysique', 'children': [{'id': 'phys.astr.co', 'label_en': 'Cosmology and Extra-Galactic Astrophysics', 'label_fr': 'Cosmologie et astrophysique extra-galactique', 'children': []}, {'id': 'phys.astr.ep', 'label_en': 'Earth and Planetary Astrophysics', 'label_fr': 'Planétologie et astrophysique de la terre', 'children': []}, {'id': 'phys.astr.ga', 'label_en': 'Galactic Astrophysics', 'label_fr': 'Astrophysique galactique', 'children': []}, {'id': 'phys.astr.he', 'label_en': 'High Energy Astrophysical Phenomena', 'label_fr': 'Phénomènes cosmiques de haute energie', 'children': []}, {'id': 'phys.astr.im', 'label_en': 'Instrumentation and Methods for Astrophysic', 'label_fr': "Instrumentation et méthodes pour l'astrophysique", 'children': []}, {'id': 'phys.astr.sr', 'label_en': 'Solar and Stellar Astrophysics', 'label_fr': 'Astrophysique stellaire et solaire', 'children': []}]}, {'id': 'phys.cond', 'label_en': 'Condensed Matter', 'label_fr': 'Matière Condensée', 'children': [{'id': 'phys.cond.cm-ds-nn', 'label_en': 'Disordered Systems and Neural Networks', 'label_fr': 'Systèmes désordonnés et réseaux de neurones', 'children': []}, {'id': 'phys.cond.cm-gen', 'label_en': 'Other', 'label_fr': 'Autre', 'children': []}, {'id': 'phys.cond.cm-ms', 'label_en': 'Materials Science', 'label_fr': 'Science des matériaux', 'children': []}, {'id': 'phys.cond.cm-msqhe', 'label_en': 'Mesoscopic Systems and Quantum Hall Effect', 'label_fr': 'Systèmes mésoscopiques et effet Hall quantique', 'children': []}, {'id': 'phys.cond.cm-s', 'label_en': 'Superconductivity', 'label_fr': 'Supraconductivité', 'children': []}, {'id': 'phys.cond.cm-sce', 'label_en': 'Strongly Correlated Electrons', 'label_fr': 'Electrons fortement corrélés', 'children': []}, {'id': 'phys.cond.cm-scm', 'label_en': 'Soft Condensed Matter', 'label_fr': 'Matière Molle', 'children': []}, {'id': 'phys.cond.cm-sm', 'label_en': 'Statistical Mechanics', 'label_fr': 'Mécanique statistique', 'children': []}, {'id': 'phys.cond.gas', 'label_en': 'Quantum Gases', 'label_fr': 'Gaz Quantiques', 'children': []}]}, {'id': 'phys.grqc', 'label_en': 'General Relativity and Quantum Cosmology', 'label_fr': 'Relativité Générale et Cosmologie Quantique', 'children': []}, {'id': 'phys.hexp', 'label_en': 'High Energy Physics - Experiment', 'label_fr': 'Physique des Hautes Energies - Expérience', 'children': []}, {'id': 'phys.hlat', 'label_en': 'High Energy Physics - Lattice', 'label_fr': 'Physique des Hautes Energies - Réseau', 'children': []}, {'id': 'phys.hphe', 'label_en': 'High Energy Physics - Phenomenology', 'label_fr': 'Physique des Hautes Energies - Phénoménologie', 'children': []}, {'id': 'phys.hthe', 'label_en': 'High Energy Physics - Theory', 'label_fr': 'Physique des Hautes Energies - Théorie', 'children': []}, {'id': 'phys.meca', 'label_en': 'Mechanics', 'label_fr': 'Mécanique', 'children': [{'id': 'phys.meca.acou', 'label_en': 'Acoustics', 'label_fr': 'Acoustique', 'children': []}, {'id': 'phys.meca.biom', 'label_en': 'Biomechanics', 'label_fr': 'Biomécanique', 'children': []}, {'id': 'phys.meca.geme', 'label_en': 'Mechanical engineering', 'label_fr': 'Génie mécanique', 'children': []}, {'id': 'phys.meca.mefl', 'label_en': 'Mechanics of the fluids', 'label_fr': 'Mécanique des fluides', 'children': []}, {'id': 'phys.meca.mema', 'label_en': 'Mechanics of materials', 'label_fr': 'Mécanique des matériaux', 'children': []}, {'id': 'phys.meca.msmeca', 'label_en': 'Materials and structures in mechanics', 'label_fr': 'Matériaux et structures en mécanique', 'children': []}, {'id': 'phys.meca.solid', 'label_en': 'Mechanics of the solides', 'label_fr': 'Mécanique des solides', 'children': []}, {'id': 'phys.meca.stru', 'label_en': 'Mechanics of the structures', 'label_fr': 'Mécanique des structures', 'children': []}, {'id': 'phys.meca.ther', 'label_en': 'Thermics', 'label_fr': 'Thermique', 'children': []}, {'id': 'phys.meca.vibr', 'label_en': 'Vibrations', 'label_fr': 'Vibrations', 'children': []}]}, {'id': 'phys.mphy', 'label_en': 'Mathematical Physics', 'label_fr': 'Physique mathématique', 'children': []}, {'id': 'phys.nexp', 'label_en': 'Nuclear Experiment', 'label_fr': 'Physique Nucléaire Expérimentale', 'children': []}, {'id': 'phys.nucl', 'label_en': 'Nuclear Theory', 'label_fr': 'Physique Nucléaire Théorique', 'children': []}, {'id': 'phys.phys', 'label_en': 'Physics', 'label_fr': 'Physique', 'children': [{'id': 'phys.phys.phys-acc-ph', 'label_en': 'Accelerator Physics', 'label_fr': 'Physique des accélérateurs', 'children': []}, {'id': 'phys.phys.phys-ao-ph', 'label_en': 'Atmospheric and Oceanic Physics', 'label_fr': 'Physique Atmosphérique et Océanique', 'children': []}, {'id': 'phys.phys.phys-atm-ph', 'label_en': 'Atomic and Molecular Clusters', 'label_fr': 'Agrégats Moléculaires et Atomiques', 'children': []}, {'id': 'phys.phys.phys-atom-ph', 'label_en': 'Atomic Physics', 'label_fr': 'Physique Atomique', 'children': []}, {'id': 'phys.phys.phys-bio-ph', 'label_en': 'Biological Physics', 'label_fr': 'Biophysique', 'children': []}, {'id': 'phys.phys.phys-chem-ph', 'label_en': 'Chemical Physics', 'label_fr': 'Chimie-Physique', 'children': []}, {'id': 'phys.phys.phys-class-ph', 'label_en': 'Classical Physics', 'label_fr': 'Physique Classique', 'children': []}, {'id': 'phys.phys.phys-comp-ph', 'label_en': 'Computational Physics', 'label_fr': 'Physique Numérique', 'children': []}, {'id': 'phys.phys.phys-data-an', 'label_en': 'Data Analysis, Statistics and Probability', 'label_fr': 'Analyse de données, Statistiques et Probabilités', 'children': []}, {'id': 'phys.phys.phys-ed-ph', 'label_en': 'Physics Education', 'label_fr': 'Enseignement de la physique', 'children': []}, {'id': 'phys.phys.phys-flu-dyn', 'label_en': 'Fluid Dynamics', 'label_fr': 'Dynamique des Fluides', 'children': []}, {'id': 'phys.phys.phys-gen-ph', 'label_en': 'General Physics', 'label_fr': 'Physique Générale', 'children': []}, {'id': 'phys.phys.phys-geo-ph', 'label_en': 'Geophysics', 'label_fr': 'Géophysique', 'children': []}, {'id': 'phys.phys.phys-hist-ph', 'label_en': 'History of Physics', 'label_fr': 'Histoire de la Physique', 'children': []}, {'id': 'phys.phys.phys-ins-det', 'label_en': 'Instrumentation and Detectors', 'label_fr': 'Instrumentations et Détecteurs', 'children': []}, {'id': 'phys.phys.phys-med-ph', 'label_en': 'Medical Physics', 'label_fr': 'Physique Médicale', 'children': []}, {'id': 'phys.phys.phys-optics', 'label_en': 'Optics', 'label_fr': 'Optique', 'children': []}, {'id': 'phys.phys.phys-plasm-ph', 'label_en': 'Plasma Physics', 'label_fr': 'Physique des plasmas', 'children': []}, {'id': 'phys.phys.phys-pop-ph', 'label_en': 'Popular Physics', 'label_fr': 'Physique : vulgarisation', 'children': []}, {'id': 'phys.phys.phys-soc-ph', 'label_en': 'Physics and Society', 'label_fr': 'Physique et Société', 'children': []}, {'id': 'phys.phys.phys-space-ph', 'label_en': 'Space Physics', 'label_fr': "Physique de l'espace", 'children': []}]}, {'id': 'phys.qphy', 'label_en': 'Quantum Physics', 'label_fr': 'Physique Quantique', 'children': []}, {'id': 'phys.hist', 'label_en': 'Physics archives', 'label_fr': 'Articles anciens', 'children': []}]}, {'id': 'scco', 'label_en': 'Cognitive science', 'label_fr': 'Sciences cognitives', 'children': [{'id': 'scco.comp', 'label_en': 'Computer science', 'label_fr': 'Informatique', 'children': []}, {'id': 'scco.ling', 'label_en': 'Linguistics', 'label_fr': 'Linguistique', 'children': []}, {'id': 'scco.neur', 'label_en': 'Neuroscience', 'label_fr': 'Neurosciences', 'children': []}, {'id': 'scco.psyc', 'label_en': 'Psychology', 'label_fr': 'Psychologie', 'children': []}]}, {'id': 'sde', 'label_en': 'Environmental Sciences', 'label_fr': "Sciences de l'environnement", 'children': [{'id': 'sde.be', 'label_en': 'Biodiversity and Ecology', 'label_fr': 'Biodiversité et Ecologie', 'children': []}, {'id': 'sde.es', 'label_en': 'Environmental and Society', 'label_fr': 'Environnement et Société', 'children': []}, {'id': 'sde.mcg', 'label_en': 'Global Changes', 'label_fr': 'Milieux et Changements globaux', 'children': []}, {'id': 'sde.ie', 'label_en': 'Environmental Engineering', 'label_fr': "Ingénierie de l'environnement", 'children': []}]}, {'id': 'sdu', 'label_en': 'Sciences of the Universe', 'label_fr': 'Planète et Univers', 'children': [{'id': 'sdu.astr', 'label_en': 'Astrophysics', 'label_fr': 'Astrophysique', 'children': [{'id': 'sdu.astr.co', 'label_en': 'Cosmology and Extra-Galactic Astrophysics', 'label_fr': 'Cosmologie et astrophysique extra-galactique', 'children': []}, {'id': 'sdu.astr.ep', 'label_en': 'Earth and Planetary Astrophysics', 'label_fr': 'Planétologie et astrophysique de la terre', 'children': []}, {'id': 'sdu.astr.ga', 'label_en': 'Galactic Astrophysics', 'label_fr': 'Astrophysique galactique', 'children': []}, {'id': 'sdu.astr.he', 'label_en': 'High Energy Astrophysical Phenomena', 'label_fr': 'Phénomènes cosmiques de haute energie', 'children': []}, {'id': 'sdu.astr.im', 'label_en': 'Instrumentation and Methods for Astrophysic', 'label_fr': "Instrumentation et méthodes pour l'astrophysique", 'children': []}, {'id': 'sdu.astr.sr', 'label_en': 'Solar and Stellar Astrophysics', 'label_fr': 'Astrophysique stellaire et solaire', 'children': []}]}, {'id': 'sdu.envi', 'label_en': 'Continental interfaces, environment', 'label_fr': 'Interfaces continentales, environnement', 'children': []}, {'id': 'sdu.ocean', 'label_en': 'Ocean, Atmosphere', 'label_fr': 'Océan, Atmosphère', 'children': []}, {'id': 'sdu.other', 'label_en': 'Other', 'label_fr': 'Autre', 'children': []}, {'id': 'sdu.stu', 'label_en': 'Earth Sciences', 'label_fr': 'Sciences de la Terre', 'children': [{'id': 'sdu.stu.ag', 'label_en': 'Applied geology', 'label_fr': 'Géologie appliquée', 'children': []}, {'id': 'sdu.stu.cl', 'label_en': 'Climatology', 'label_fr': 'Climatologie', 'children': []}, {'id': 'sdu.stu.gc', 'label_en': 'Geochemistry', 'label_fr': 'Géochimie', 'children': []}, {'id': 'sdu.stu.gl', 'label_en': 'Glaciology', 'label_fr': 'Glaciologie', 'children': []}, {'id': 'sdu.stu.gm', 'label_en': 'Geomorphology', 'label_fr': 'Géomorphologie', 'children': []}, {'id': 'sdu.stu.gp', 'label_en': 'Geophysics', 'label_fr': 'Géophysique', 'children': []}, {'id': 'sdu.stu.hy', 'label_en': 'Hydrology', 'label_fr': 'Hydrologie', 'children': []}, {'id': 'sdu.stu.me', 'label_en': 'Meteorology', 'label_fr': 'Météorologie', 'children': []}, {'id': 'sdu.stu.mi', 'label_en': 'Mineralogy', 'label_fr': 'Minéralogie', 'children': []}, {'id': 'sdu.stu.oc', 'label_en': 'Oceanography', 'label_fr': 'Océanographie', 'children': []}, {'id': 'sdu.stu.pe', 'label_en': 'Petrography', 'label_fr': 'Pétrographie', 'children': []}, {'id': 'sdu.stu.pg', 'label_en': 'Paleontology', 'label_fr': 'Paléontologie', 'children': []}, {'id': 'sdu.stu.pl', 'label_en': 'Planetology', 'label_fr': 'Planétologie', 'children': []}, {'id': 'sdu.stu.st', 'label_en': 'Stratigraphy', 'label_fr': 'Stratigraphie', 'children': []}, {'id': 'sdu.stu.te', 'label_en': 'Tectonics', 'label_fr': 'Tectonique', 'children': []}, {'id': 'sdu.stu.vo', 'label_en': 'Volcanology', 'label_fr': 'Volcanologie', 'children': []}]}]}, {'id': 'sdv', 'label_en': 'Life Sciences', 'label_fr': 'Sciences du Vivant', 'children': [{'id': 'sdv.aen', 'label_en': 'Food and Nutrition', 'label_fr': 'Alimentation et Nutrition', 'children': []}, {'id': 'sdv.ba', 'label_en': 'Animal biology', 'label_fr': 'Biologie animale', 'children': [{'id': 'sdv.ba.mvsa', 'label_en': 'Veterinary medicine and animal Health', 'label_fr': 'Médecine vétérinaire et santé animal', 'children': []}, {'id': 'sdv.ba.zi', 'label_en': 'Invertebrate Zoology', 'label_fr': 'Zoologie des invertébrés', 'children': []}, {'id': 'sdv.ba.zv', 'label_en': 'Vertebrate Zoology', 'label_fr': 'Zoologie des vertébrés', 'children': []}]}, {'id': 'sdv.bbm', 'label_en': 'Biochemistry, Molecular Biology', 'label_fr': 'Biochimie, Biologie Moléculaire', 'children': [{'id': 'sdv.bbm.bc', 'label_en': 'Biomolecules', 'label_fr': 'Biochimie', 'children': []}, {'id': 'sdv.bbm.bm', 'label_en': 'Molecular biology', 'label_fr': 'Biologie moléculaire', 'children': []}, {'id': 'sdv.bbm.bp', 'label_en': 'Biophysics', 'label_fr': 'Biophysique', 'children': []}, {'id': 'sdv.bbm.bs', 'label_en': 'Biomolecules', 'label_fr': 'Biologie structurale', 'children': []}, {'id': 'sdv.bbm.gtp', 'label_en': 'Genomics', 'label_fr': 'Génomique, Transcriptomique et Protéomique', 'children': []}, {'id': 'sdv.bbm.mn', 'label_en': 'Molecular Networks', 'label_fr': 'Réseaux moléculaires', 'children': []}]}, {'id': 'sdv.bc', 'label_en': 'Cellular Biology', 'label_fr': 'Biologie cellulaire', 'children': [{'id': 'sdv.bc.bc', 'label_en': 'Subcellular Processes', 'label_fr': 'Organisation et fonctions cellulaires', 'children': []}, {'id': 'sdv.bc.ic', 'label_en': 'Cell Behavior', 'label_fr': 'Interactions cellulaires', 'children': []}]}, {'id': 'sdv.bdd', 'label_en': 'Development Biology', 'label_fr': 'Biologie du développement', 'children': [{'id': 'sdv.bdd.eo', 'label_en': 'Embryology and Organogenesis', 'label_fr': 'Embryologie et organogenèse', 'children': []}, {'id': 'sdv.bdd.gam', 'label_en': 'Gametogenesis', 'label_fr': 'Gamétogenèse', 'children': []}, {'id': 'sdv.bdd.mor', 'label_en': 'Morphogenesis', 'label_fr': 'Morphogenèse', 'children': []}]}, {'id': 'sdv.bdlr', 'label_en': 'Reproductive Biology', 'label_fr': 'Biologie de la reproduction', 'children': [{'id': 'sdv.bdlr.ra', 'label_en': 'Asexual reproduction', 'label_fr': 'Reproduction asexuée', 'children': []}, {'id': 'sdv.bdlr.rs', 'label_en': 'Sexual reproduction', 'label_fr': 'Reproduction sexuée', 'children': []}]}, {'id': 'sdv.bibs', 'label_en': 'Quantitative Methods', 'label_fr': 'Bio-Informatique, Biologie Systémique', 'children': []}, {'id': 'sdv.bid', 'label_en': 'Biodiversity', 'label_fr': 'Biodiversité', 'children': [{'id': 'sdv.bid.evo', 'label_en': 'Populations and Evolution', 'label_fr': 'Evolution', 'children': []}, {'id': 'sdv.bid.spt', 'label_en': 'Systematics, Phylogenetics and taxonomy', 'label_fr': 'Systématique, phylogénie et taxonomie', 'children': []}]}, {'id': 'sdv.bio', 'label_en': 'Biotechnology', 'label_fr': 'Biotechnologies', 'children': []}, {'id': 'sdv.bv', 'label_en': 'Vegetal Biology', 'label_fr': 'Biologie végétale', 'children': [{'id': 'sdv.bv.ap', 'label_en': 'Plant breeding', 'label_fr': 'Amélioration des plantes', 'children': []}, {'id': 'sdv.bv.bot', 'label_en': 'Botanics', 'label_fr': 'Botanique', 'children': []}, {'id': 'sdv.bv.pep', 'label_en': 'Phytopathology and phytopharmacy', 'label_fr': 'Phytopathologie et phytopharmacie', 'children': []}]}, {'id': 'sdv.can', 'label_en': 'Cancer', 'label_fr': 'Cancer', 'children': []}, {'id': 'sdv.ee', 'label_en': 'Ecology, environment', 'label_fr': 'Ecologie, Environnement', 'children': [{'id': 'sdv.ee.bio', 'label_en': 'Bioclimatology', 'label_fr': 'Bioclimatologie', 'children': []}, {'id': 'sdv.ee.eco', 'label_en': 'Ecosystems', 'label_fr': 'Ecosystèmes', 'children': []}, {'id': 'sdv.ee.ieo', 'label_en': 'Symbiosis', 'label_fr': 'Interactions entre organismes', 'children': []}, {'id': 'sdv.ee.sant', 'label_en': 'Health', 'label_fr': 'Santé', 'children': []}]}, {'id': 'sdv.eth', 'label_en': 'Ethics', 'label_fr': 'Ethique', 'children': []}, {'id': 'sdv.gen', 'label_en': 'Genetics', 'label_fr': 'Génétique', 'children': [{'id': 'sdv.gen.ga', 'label_en': 'Animal genetics', 'label_fr': 'Génétique animale', 'children': []}, {'id': 'sdv.gen.gh', 'label_en': 'Human genetics', 'label_fr': 'Génétique humaine', 'children': []}, {'id': 'sdv.gen.gpl', 'label_en': 'Plants genetics', 'label_fr': 'Génétique des plantes', 'children': []}, {'id': 'sdv.gen.gpo', 'label_en': 'Populations and Evolution', 'label_fr': 'Génétique des populations', 'children': []}]}, {'id': 'sdv.ib', 'label_en': 'Bioengineering', 'label_fr': 'Ingénierie biomédicale', 'children': [{'id': 'sdv.ib.bio', 'label_en': 'Biomaterials', 'label_fr': 'Biomatériaux', 'children': []}, {'id': 'sdv.ib.ima', 'label_en': 'Imaging', 'label_fr': 'Imagerie', 'children': []}, {'id': 'sdv.ib.mn', 'label_en': 'Nuclear medicine', 'label_fr': 'Médecine nucléaire', 'children': []}]}, {'id': 'sdv.ida', 'label_en': 'Food engineering', 'label_fr': 'Ingénierie des aliments', 'children': []}, {'id': 'sdv.imm', 'label_en': 'Immunology', 'label_fr': 'Immunologie', 'children': [{'id': 'sdv.imm.all', 'label_en': 'Allergology', 'label_fr': 'Allergologie', 'children': []}, {'id': 'sdv.imm.ia', 'label_en': 'Adaptive immunology', 'label_fr': 'Immunité adaptative', 'children': []}, {'id': 'sdv.imm.ii', 'label_en': 'Innate immunity', 'label_fr': 'Immunité innée', 'children': []}, {'id': 'sdv.imm.imm', 'label_en': 'Immunotherapy', 'label_fr': 'Immunothérapie', 'children': []}, {'id': 'sdv.imm.vac', 'label_en': 'Vaccinology', 'label_fr': 'Vaccinologie', 'children': []}]}, {'id': 'sdv.mhep', 'label_en': 'Human health and pathology', 'label_fr': 'Médecine humaine et pathologie', 'children': [{'id': 'sdv.mhep.aha', 'label_en': 'Tissues and Organs', 'label_fr': 'Anatomie, Histologie, Anatomopathologie', 'children': []}, {'id': 'sdv.mhep.chi', 'label_en': 'Surgery', 'label_fr': 'Chirurgie', 'children': []}, {'id': 'sdv.mhep.csc', 'label_en': 'Cardiology and cardiovascular system', 'label_fr': 'Cardiologie et système cardiovasculaire', 'children': []}, {'id': 'sdv.mhep.derm', 'label_en': 'Dermatology', 'label_fr': 'Dermatologie', 'children': []}, {'id': 'sdv.mhep.em', 'label_en': 'Endocrinology and metabolism', 'label_fr': 'Endocrinologie et métabolisme', 'children': []}, {'id': 'sdv.mhep.geg', 'label_en': 'Geriatry and gerontology', 'label_fr': 'Gériatrie et gérontologie', 'children': []}, {'id': 'sdv.mhep.geo', 'label_en': 'Gynecology and obstetrics', 'label_fr': 'Gynécologie et obstétrique', 'children': []}, {'id': 'sdv.mhep.heg', 'label_en': 'Hépatology and Gastroenterology', 'label_fr': 'Hépatologie et Gastroentérologie', 'children': []}, {'id': 'sdv.mhep.hem', 'label_en': 'Hematology', 'label_fr': 'Hématologie', 'children': []}, {'id': 'sdv.mhep.me', 'label_en': 'Emerging diseases', 'label_fr': 'Maladies émergentes', 'children': []}, {'id': 'sdv.mhep.mi', 'label_en': 'Infectious diseases', 'label_fr': 'Maladies infectieuses', 'children': []}, {'id': 'sdv.mhep.os', 'label_en': 'Sensory Organs', 'label_fr': 'Organes des sens', 'children': []}, {'id': 'sdv.mhep.ped', 'label_en': 'Pediatrics', 'label_fr': 'Pédiatrie', 'children': []}, {'id': 'sdv.mhep.phy', 'label_en': 'Tissues and Organs', 'label_fr': 'Physiologie', 'children': []}, {'id': 'sdv.mhep.psm', 'label_en': 'Psychiatrics and mental health', 'label_fr': 'Psychiatrie et santé mentale', 'children': []}, {'id': 'sdv.mhep.psr', 'label_en': 'Pulmonology and respiratory tract', 'label_fr': 'Pneumologie et système respiratoire', 'children': []}, {'id': 'sdv.mhep.rsoa', 'label_en': 'Rhumatology and musculoskeletal system', 'label_fr': 'Rhumatologie et système ostéo-articulaire', 'children': []}, {'id': 'sdv.mhep.un', 'label_en': 'Urology and Nephrology', 'label_fr': 'Urologie et Néphrologie', 'children': []}]}, {'id': 'sdv.mp', 'label_en': 'Microbiology and Parasitology', 'label_fr': 'Microbiologie et Parasitologie', 'children': [{'id': 'sdv.mp.bac', 'label_en': 'Bacteriology', 'label_fr': 'Bactériologie', 'children': []}, {'id': 'sdv.mp.myc', 'label_en': 'Mycology', 'label_fr': 'Mycologie', 'children': []}, {'id': 'sdv.mp.par', 'label_en': 'Parasitology', 'label_fr': 'Parasitologie', 'children': []}, {'id': 'sdv.mp.pro', 'label_en': 'Protistology', 'label_fr': 'Protistologie', 'children': []}, {'id': 'sdv.mp.vir', 'label_en': 'Virology', 'label_fr': 'Virologie', 'children': []}]}, {'id': 'sdv.neu', 'label_en': 'Neurons and Cognition', 'label_fr': 'Neurosciences', 'children': [{'id': 'sdv.neu.nb', 'label_en': 'Neurobiology', 'label_fr': 'Neurobiologie', 'children': []}, {'id': 'sdv.neu.pc', 'label_en': 'Psychology and behavior', 'label_fr': 'Psychologie et comportements', 'children': []}, {'id': 'sdv.neu.sc', 'label_en': 'Cognitive Sciences', 'label_fr': 'Sciences cognitives', 'children': []}]}, {'id': 'sdv.ot', 'label_en': 'Other', 'label_fr': 'Autre', 'children': []}, {'id': 'sdv.sa', 'label_en': 'Agricultural sciences', 'label_fr': 'Sciences agricoles', 'children': [{'id': 'sdv.sa.aep', 'label_en': 'Agriculture, economy and politics', 'label_fr': 'Agriculture, économie et politique', 'children': []}, {'id': 'sdv.sa.agro', 'label_en': 'Agronomy', 'label_fr': 'Agronomie', 'children': []}, {'id': 'sdv.sa.hort', 'label_en': 'Horticulture', 'label_fr': 'Horticulture', 'children': []}, {'id': 'sdv.sa.sds', 'label_en': 'Soil study', 'label_fr': 'Science des sols', 'children': []}, {'id': 'sdv.sa.sf', 'label_en': 'Silviculture, forestry', 'label_fr': 'Sylviculture, foresterie', 'children': []}, {'id': 'sdv.sa.spa', 'label_en': 'Animal production studies', 'label_fr': 'Science des productions animales', 'children': []}, {'id': 'sdv.sa.sta', 'label_en': 'Sciences and technics of agriculture', 'label_fr': "Sciences et techniques de l'agriculture", 'children': []}, {'id': 'sdv.sa.stp', 'label_en': 'Sciences and technics of fishery', 'label_fr': 'Sciences et techniques des pêches', 'children': []}, {'id': 'sdv.sa.zoo', 'label_en': 'Zootechny', 'label_fr': 'Zootechnie', 'children': []}]}, {'id': 'sdv.sp', 'label_en': 'Pharmaceutical sciences', 'label_fr': 'Sciences pharmaceutiques', 'children': [{'id': 'sdv.sp.med', 'label_en': 'Medication', 'label_fr': 'Médicaments', 'children': []}, {'id': 'sdv.sp.pg', 'label_en': 'Galenic pharmacology', 'label_fr': 'Pharmacie galénique', 'children': []}, {'id': 'sdv.sp.pharma', 'label_en': 'Pharmacology', 'label_fr': 'Pharmacologie', 'children': []}]}, {'id': 'sdv.spee', 'label_en': 'Santé publique et épidémiologie', 'label_fr': 'Santé publique et épidémiologie', 'children': []}, {'id': 'sdv.tox', 'label_en': 'Toxicology', 'label_fr': 'Toxicologie', 'children': [{'id': 'sdv.tox.eco', 'label_en': 'Ecotoxicology', 'label_fr': 'Ecotoxicologie', 'children': []}, {'id': 'sdv.tox.tca', 'label_en': 'Toxicology and food chain', 'label_fr': 'Toxicologie et chaîne alimentaire', 'children': []}, {'id': 'sdv.tox.tvm', 'label_en': 'Vegetal toxicology and mycotoxicology', 'label_fr': 'Toxicologie végétale et mycotoxicologie', 'children': []}]}]}, {'id': 'shs', 'label_en': 'Humanities and Social Sciences', 'label_fr': "Sciences de l'Homme et Société", 'children': [{'id': 'shs.anthro-bio', 'label_en': 'Biological anthropology', 'label_fr': 'Anthropologie biologique', 'children': []}, {'id': 'shs.anthro-se', 'label_en': 'Social Anthropology and ethnology', 'label_fr': 'Anthropologie sociale et ethnologie', 'children': []}, {'id': 'shs.archeo', 'label_en': 'Archaeology and Prehistory', 'label_fr': 'Archéologie et Préhistoire', 'children': []}, {'id': 'shs.archi', 'label_en': 'Architecture, space management', 'label_fr': "Architecture, aménagement de l'espace", 'children': []}, {'id': 'shs.art', 'label_en': 'Art and art history', 'label_fr': "Art et histoire de l'art", 'children': []}, {'id': 'shs.class', 'label_en': 'Classical studies', 'label_fr': 'Etudes classiques', 'children': []}, {'id': 'shs.demo', 'label_en': 'Demography', 'label_fr': 'Démographie', 'children': []}, {'id': 'shs.droit', 'label_en': 'Law', 'label_fr': 'Droit', 'children': []}, {'id': 'shs.eco', 'label_en': 'Economics and Finance', 'label_fr': 'Economies et finances', 'children': []}, {'id': 'shs.edu', 'label_en': 'Education', 'label_fr': 'Education', 'children': []}, {'id': 'shs.envir', 'label_en': 'Environmental studies', 'label_fr': "Etudes de l'environnement", 'children': []}, {'id': 'shs.genre', 'label_en': 'Gender studies', 'label_fr': 'Etudes sur le genre', 'children': []}, {'id': 'shs.geo', 'label_en': 'Geography', 'label_fr': 'Géographie', 'children': []}, {'id': 'shs.gestion', 'label_en': 'Business administration', 'label_fr': 'Gestion et management', 'children': []}, {'id': 'shs.hisphilso', 'label_en': 'History, Philosophy and Sociology of Sciences', 'label_fr': 'Histoire, Philosophie et Sociologie des sciences', 'children': []}, {'id': 'shs.hist', 'label_en': 'History', 'label_fr': 'Histoire', 'children': []}, {'id': 'shs.info', 'label_en': 'Library and information sciences', 'label_fr': "Sciences de l'information et de la communication", 'children': []}, {'id': 'shs.langue', 'label_en': 'Linguistics', 'label_fr': 'Linguistique', 'children': []}, {'id': 'shs.litt', 'label_en': 'Literature', 'label_fr': 'Littératures', 'children': []}, {'id': 'shs.museo', 'label_en': 'Cultural heritage and museology', 'label_fr': 'Héritage culturel et muséologie', 'children': []}, {'id': 'shs.musiq', 'label_en': 'Musicology and performing arts', 'label_fr': 'Musique, musicologie et arts de la scène', 'children': []}, {'id': 'shs.phil', 'label_en': 'Philosophy', 'label_fr': 'Philosophie', 'children': []}, {'id': 'shs.psy', 'label_en': 'Psychology', 'label_fr': 'Psychologie', 'children': []}, {'id': 'shs.relig', 'label_en': 'Religions', 'label_fr': 'Religions', 'children': []}, {'id': 'shs.scipo', 'label_en': 'Political science', 'label_fr': 'Science politique', 'children': []}, {'id': 'shs.socio', 'label_en': 'Sociology', 'label_fr': 'Sociologie', 'children': []}, {'id': 'shs.stat', 'label_en': 'Methods and statistics', 'label_fr': 'Méthodes et statistiques', 'children': []}]}, {'id': 'spi', 'label_en': 'Engineering Sciences', 'label_fr': "Sciences de l'ingénieur", 'children': [{'id': 'spi.acou', 'label_en': 'Acoustics', 'label_fr': 'Acoustique', 'children': []}, {'id': 'spi.auto', 'label_en': 'Automatic', 'label_fr': 'Automatique / Robotique', 'children': []}, {'id': 'spi.elec', 'label_en': 'Electromagnetism', 'label_fr': 'Electromagnétisme', 'children': []}, {'id': 'spi.fluid', 'label_en': 'Reactive fluid environment', 'label_fr': 'Milieux fluides et réactifs', 'children': []}, {'id': 'spi.gproc', 'label_en': 'Chemical and Process Engineering', 'label_fr': 'Génie des procédés', 'children': []}, {'id': 'spi.mat', 'label_en': 'Materials', 'label_fr': 'Matériaux', 'children': []}, {'id': 'spi.meca', 'label_en': 'Mechanics', 'label_fr': 'Mécanique', 'children': [{'id': 'spi.meca.biom', 'label_en': 'Biomechanics', 'label_fr': 'Biomécanique', 'children': []}, {'id': 'spi.meca.geme', 'label_en': 'Mechanical engineering', 'label_fr': 'Génie mécanique', 'children': []}, {'id': 'spi.meca.mefl', 'label_en': 'Fluids mechanics', 'label_fr': 'Mécanique des fluides', 'children': []}, {'id': 'spi.meca.mema', 'label_en': 'Mechanics of materials', 'label_fr': 'Mécanique des matériaux', 'children': []}, {'id': 'spi.meca.msmeca', 'label_en': 'Materials and structures in mechanics', 'label_fr': 'Matériaux et structures en mécanique', 'children': []}, {'id': 'spi.meca.solid', 'label_en': 'Mechanics of the solides', 'label_fr': 'Mécanique des solides', 'children': []}, {'id': 'spi.meca.stru', 'label_en': 'Mechanics of the structures', 'label_fr': 'Mécanique des structures', 'children': []}, {'id': 'spi.meca.ther', 'label_en': 'Thermics', 'label_fr': 'Thermique', 'children': []}, {'id': 'spi.meca.vibr', 'label_en': 'Vibrations', 'label_fr': 'Vibrations', 'children': []}]}, {'id': 'spi.nano', 'label_en': 'Micro and nanotechnologies/Microelectronics', 'label_fr': 'Micro et nanotechnologies/Microélectronique', 'children': []}, {'id': 'spi.nrj', 'label_en': 'Electric power', 'label_fr': 'Energie électrique', 'children': []}, {'id': 'spi.opti', 'label_en': 'Optics / Photonic', 'label_fr': 'Optique / photonique', 'children': []}, {'id': 'spi.other', 'label_en': 'Other', 'label_fr': 'Autre', 'children': []}, {'id': 'spi.plasma', 'label_en': 'Plasmas', 'label_fr': 'Plasmas', 'children': []}, {'id': 'spi.signal', 'label_en': 'Signal and Image processing', 'label_fr': "Traitement du signal et de l'image", 'children': []}, {'id': 'spi.tron', 'label_en': 'Electronics', 'label_fr': 'Electronique', 'children': []}, {'id': 'spi.gciv', 'label_en': 'Civil Engineering', 'label_fr': 'Génie civil', 'children': [{'id': 'spi.gciv.ch', 'label_en': 'Construction hydraulique', 'label_fr': 'Construction hydraulique', 'children': []}, {'id': 'spi.gciv.cd', 'label_en': 'Construction durable', 'label_fr': 'Construction durable', 'children': []}, {'id': 'spi.gciv.dv', 'label_en': 'Dynamique, vibrations', 'label_fr': 'Dynamique, vibrations', 'children': []}, {'id': 'spi.gciv.ec', 'label_en': 'Eco-conception', 'label_fr': 'Eco-conception', 'children': []}, {'id': 'spi.gciv.gcn', 'label_en': 'Génie civil nucléaire', 'label_fr': 'Génie civil nucléaire', 'children': []}, {'id': 'spi.gciv.geotech', 'label_en': 'Géotechnique', 'label_fr': 'Géotechnique', 'children': []}, {'id': 'spi.gciv.it', 'label_en': 'Infrastructures de transport', 'label_fr': 'Infrastructures de transport', 'children': []}, {'id': 'spi.gciv.mat', 'label_en': 'Matériaux composites et construction', 'label_fr': 'Matériaux composites et construction', 'children': []}, {'id': 'spi.gciv.rhea', 'label_en': 'Rehabilitation', 'label_fr': 'Réhabilitation', 'children': []}, {'id': 'spi.gciv.risq', 'label_en': 'Risques', 'label_fr': 'Risques', 'children': []}, {'id': 'spi.gciv.struct', 'label_en': 'Structures', 'label_fr': 'Structures', 'children': []}]}]}, {'id': 'stat', 'label_en': 'Statistics', 'label_fr': 'Statistiques', 'children': [{'id': 'stat.ot', 'label_en': 'Other Statistics', 'label_fr': 'Autres', 'children': []}, {'id': 'stat.ap', 'label_en': 'Applications', 'label_fr': 'Applications', 'children': []}, {'id': 'stat.co', 'label_en': 'Computation', 'label_fr': 'Calcul', 'children': []}, {'id': 'stat.me', 'label_en': 'Methodology', 'label_fr': 'Méthodologie', 'children': []}, {'id': 'stat.th', 'label_en': 'Statistics Theory', 'label_fr': 'Théorie', 'children': []}, {'id': 'stat.ml', 'label_en': 'Machine Learning', 'label_fr': 'Machine Learning', 'children': []}]}, {'id': 'qfin', 'label_en': 'Quantitative Finance', 'label_fr': 'Économie et finance quantitative', 'children': [{'id': 'qfin.cp', 'label_en': 'Computational Finance', 'label_fr': 'Finance quantitative', 'children': []}, {'id': 'qfin.gn', 'label_en': 'General Finance', 'label_fr': 'Finance', 'children': []}, {'id': 'qfin.pm', 'label_en': 'Portfolio Management', 'label_fr': 'Gestion de portefeuilles', 'children': []}, {'id': 'qfin.pr', 'label_en': 'Pricing of Securities', 'label_fr': 'Pricing', 'children': []}, {'id': 'qfin.rm', 'label_en': 'Risk Management', 'label_fr': 'Gestion des risques', 'children': []}, {'id': 'qfin.st', 'label_en': 'Statistical Finance', 'label_fr': 'Econométrie de la finance', 'children': []}, {'id': 'qfin.tr', 'label_en': 'Trading and Market Microstructure', 'label_fr': 'Microstructure des marchés', 'children': []}]}]}

        guidingDomains = []

        if 'guidingDomains' in entity:
            guidingDomains = entity['guidingDomains']

        return render(request, 'check.html', {'data': data, 'type': type, 'id': id, 'from': dateFrom, 'to': dateTo,
                                              'entity': entity,
                                              'domains': domains,
                                              'guidingDomains': guidingDomains,
                                              'startDate': start_date,
                                              'timeRange': "from:'" + dateFrom + "',to:'" + dateTo + "'"})


    elif data == "references":

        # Get references
        ref_param = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "match_phrase": {
                                ext_key: entity[key]
                            }
                        },
                        {
                            "match": {
                                "validated": False
                            }
                        },
                        {
                            "range": {
                                "submittedDate_tdate": {
                                    "gte": dateFrom,
                                    "lt": dateTo
                                }
                            }
                        }
                    ]
                }
            }
        }

        count = es.count(index=structId  +"*-documents", body=ref_param)['count']

        references = es.search(index= structId  +"*-documents", body=ref_param, size=count)

        references_cleaned = []

        for ref in references['hits']['hits']:
            references_cleaned.append(ref['_source'])
        # /

        return render(request, 'check.html', {'data': data, 'type': type, 'id': id, 'from': dateFrom, 'to': dateTo,
                                              'entity': entity,
                                              'references': references_cleaned, 'startDate': start_date,
                                              'timeRange': "from:'" + dateFrom + "',to:'" + dateTo + "'"})

    else:
        return redirect('unknown')


def search(request):

    # Connect to DB
    es = esConnector()

    date_param = {
        "aggs" : {
            "min_date": {"min": {"field": "submittedDate_tdate"}},
        }
    }

    min_date = es.search(index= structId  +"-*-documents", body=date_param, size=0)['aggregations']['min_date']['value_as_string']

    # Get parameters
    if 'from' in request.GET:
        dateFrom = request.GET['from']
    else:
        dateFrom = min_date[0:4] + '-01-01'

    if 'to' in request.GET:
        dateTo = request.GET['to']
    else:
        dateTo = datetime.today().strftime('%Y-%m-%d')

    if request.method == 'POST':

        # Connect to DB
        es = esConnector()

        index = request.POST.get("f_index")
        search = request.POST.get("f_search")

        if "documents" in index: # == 'documents':
            search_param = {
                "query":{"bool":{"must": [{"query_string": {"query": search}}],"filter":[{"match":{"validated":"true"}}]}}
            }
        elif "researchers" in index: #=='researchers':
            search_param = {
                "query": {"query_string": {"query": search}}
            }
        else:
            search_param = {
                "query": {"query_string": {"query": search}}
            }

        p_res = es.count(index=index, body=search_param)
        res = es.search(index=index, body=search_param, size=p_res['count'])

        res_cleaned = []

        for result in res['hits']['hits']:
            res_cleaned.append(result['_source'])
        messages.add_message(request, messages.INFO, 'Résultats de la recherche "{}" dans la collection "{}"'.format(search,index))
        return render(request, 'search.html', {'form': forms.search(val=search), 'count': p_res['count'], 'timeRange': "from:'" + dateFrom + "',to:'" + dateTo + "'", 'filter': search, 'index': index, 'search': search,'results': res_cleaned, 'from': dateFrom, 'to': dateTo, 'startDate': min_date, 'from': dateFrom, 'to': dateTo})


    return render(request, 'search.html', {'form': forms.search(), 'from': dateFrom, 'to': dateTo, 'startDate': min_date, 'from': dateFrom, 'to': dateTo, 'filter': ''})


@xframe_options_exempt
def terminology(request):
    # Get parameters
    if 'type' in request.GET:
        type = request.GET['type']
    else:
        return redirect('unknown')
    if 'export' in request.GET:
        export = request.GET['export']
    else:
        export = False
    if 'id' in request.GET:
        id = request.GET['id']
    else:
        return redirect('unknown')
    # /

    # Connect to DB
    es = esConnector()

    # Get scope informations
    if type == "rsr":
        scope_param = {
            "query": {
                "match": {
                    "_id": id
                }
            }
        }

        key = 'halId_s'
        ext_key = "harvested_from_ids"

        res = es.search(index= structId  +"-*-researchers", body=scope_param)
        entity = res['hits']['hits'][0]['_source']

    elif type == "lab":
        scope_param = {
            "query": {
                "match": {
                    "halStructId": id
                }
            }
        }

        key = "halStructId"
        ext_key = "harvested_from_ids"

        res = es.search(index= structId  +"-*-laboratories", body=scope_param)
        entity = res['hits']['hits'][0]['_source']
    # /

    hasToConfirm = False

    if type == "rsr":
        hasToConfirm_param = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "match_phrase": {
                                "harvested_from_ids": entity['halId_s']
                            }
                        },
                        {
                            "match": {
                                "validated": False
                            }
                        }
                    ]
                }
            }
        }

    if type == "lab":
        hasToConfirm_param = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "match_phrase": {
                                "harvested_from_ids": entity['halStructId']
                            }
                        },
                        {
                            "match": {
                                "validated": False
                            }
                        }
                    ]
                }
            }
        }

    if es.count(index="*-documents", body=hasToConfirm_param)['count'] > 0:
        hasToConfirm = True

    # Get first submittedDate_tdate date
    if type == "rsr":
        start_date_param = {
            "size": 1,
            "sort": [
                {"submittedDate_tdate": {"order": "asc"}}
            ],
            "query": {
                "match_phrase": {"harvested_from_ids": entity['halId_s']}
            }
        }
    elif type == "lab":
        start_date_param = {
            "size": 1,
            "sort": [
                {"submittedDate_tdate": {"order": "asc"}}
            ],
            "query": {
                "match_phrase": {"harvested_from_ids": entity['halStructId']}
            }
        }

    res = es.search(index= structId  +"-*-documents", body=start_date_param)
    start_date = res['hits']['hits'][0]['_source']['submittedDate_tdate']
    # /

    # Get parameters
    if 'from' in request.GET:
        dateFrom = request.GET['from']
    else:
        dateFrom = start_date[0:4] + '-01-01'

    if 'to' in request.GET:
        dateTo = request.GET['to']
    else:
        dateTo = datetime.today().strftime('%Y-%m-%d')
    # /

    if type == "lab":
        entity['concepts'] = json.dumps(entity['concepts'] )

    if type == "rsr":
        entity['concepts'] = json.dumps(entity['concepts'])

    entity['concepts'] = json.loads(entity['concepts'])

    if 'children' in list(entity['concepts']):
        for children in list(entity['concepts']['children']):
            if 'state' in children:
                entity['concepts']['children'].remove(children)

            if 'researchers' in children:
                state = 'invalidated'
                for rsr in children['researchers']:
                    if 'state' not in rsr:
                        state = None
                if state:
                    entity['concepts']['children'].remove(children)

            if 'children' in children:
                for children1 in list(children['children']):
                    if 'state' in children1:
                        children['children'].remove(children1)

                    if 'researchers' in children1:
                        state = 'invalidated'
                        for rsr in children1['researchers']:
                            if 'state' not in rsr:
                                state = None
                        if state:
                            children['children'].remove(children1)

                    if 'children' in children1:
                        for children2 in list(children1['children']):

                            if 'state' in children2:
                                children1['children'].remove(children2)

                            if 'researchers' in children2:
                                state = 'invalidated'
                                for rsr in children2['researchers']:
                                    if 'state' not in rsr:
                                        state = None
                                if state:
                                    children1['children'].remove(children2)

    if export:
        return render(request, 'terminology_ext.html', {'type': type, 'id': id, 'from': dateFrom, 'to': dateTo,
                                                        'entity': entity,
                                                        'hasToConfirm': hasToConfirm,
                                                        'startDate': start_date,
                                                        'timeRange': "from:'" + dateFrom + "',to:'" + dateTo + "'"})
    else:
        return render(request, 'terminology.html', {'type': type, 'id': id, 'from': dateFrom, 'to': dateTo,
                                                    'entity': entity,
                                                    'hasToConfirm': hasToConfirm,
                                                    'startDate': start_date,
                                                    'timeRange': "from:'" + dateFrom + "',to:'" + dateTo + "'"})


# Redirects

def validateReferences(request):
    # Get parameters
    if 'type' in request.GET:
        type = request.GET['type']
    else:
        return redirect('unknown')
    if 'id' in request.GET:
        id = request.GET['id']
    else:
        return redirect('unknown')
    if 'data' in request.GET:
        data = request.GET['data']
    else:
        data = -1
    if 'from' in request.GET:
        dateFrom = request.GET['from']
    if 'to' in request.GET:
        dateTo = request.GET['to']

    # Connect to DB
    es = esConnector()

    if type == "rsr":
        scope_param = {
            "query": {
                "match": {
                    "_id": id
                }
            }
        }

        res = es.search(index= structId  +"-*-researchers", body=scope_param)
        entity = res['hits']['hits'][0]['_source']

        if request.method == 'POST':
            toValidate = request.POST.get("toValidate", "").split(",")
            for docid in toValidate:
                es.update(index=structId + '-' + entity['labHalId'] + "-researchers-documents", refresh='wait_for', id=docid,
                          body={"doc": {"validated": True}})

    if type == "lab":
        scope_param = {
            "query": {
                "match": {
                    "_id": id
                }
            }
        }

        res = es.search(index= structId  +"-*-laboratories", body=scope_param)
        entity = res['hits']['hits'][0]['_source']

        if request.method == 'POST':
            toValidate = request.POST.get("toValidate", "").split(",")
            for docid in toValidate:
                es.update(index=structId + '-' + id  +  "-documents", refresh='wait_for', id=docid,
                          body={"doc": {"validated": True}})

    return redirect('/check/?type=' + type + '&id=' + id  + '&from=' + dateFrom + '&to=' + dateTo + '&data=' + data)

def validateGuidingDomains(request):
    # Get parameters
    if 'type' in request.GET:
        type = request.GET['type']
    else:
        return redirect('unknown')
    if 'id' in request.GET:
        id = request.GET['id']
    else:
        return redirect('unknown')
    if 'data' in request.GET:
        data = request.GET['data']
    else:
        data = -1
    if 'from' in request.GET:
        dateFrom = request.GET['from']
    if 'to' in request.GET:
        dateTo = request.GET['to']

    # Connect to DB
    es = esConnector()

    if request.method == 'POST':

        toValidate = request.POST.get("toValidate", "").split(',')

        if type == "rsr":
            scope_param = {
                "query": {
                    "match": {
                        "_id": id
                    }
                }
            }

            res = es.search(index= structId  +"-*-researchers", body=scope_param)
            entity = res['hits']['hits'][0]['_source']

            es.update(index=structId + "-" + entity['labHalId'] + "-researchers", refresh='wait_for', id=id,
                      body={"doc": {"guidingDomains": toValidate}})

        if type == "lab":
            es.update(index=structId + "-" + id  + "-laboratories", refresh='wait_for', id=id,
                      body={"doc": {"guidingDomains": toValidate}})

    return redirect('/check/?type=' + type + '&id=' + id  + '&from=' + dateFrom + '&to=' + dateTo + '&data=' + data)


def invalidateConcept(request):

    # Get parameters
    if 'type' in request.GET:
        type = request.GET['type']
    else:
        return redirect('unknown')
    if 'id' in request.GET:
        id = request.GET['id']
    else:
        return redirect('unknown')
    if 'data' in request.GET:
        data = request.GET['data']
    else:
        data = -1
    if 'from' in request.GET:
        dateFrom = request.GET['from']
    if 'to' in request.GET:
        dateTo = request.GET['to']

    # Connect to DB
    es = esConnector()

    # Get scope informations
    if type == "rsr":
        scope_param = {
            "query": {
                "match": {
                    "_id": id
                }
            }
        }


        res = es.search(index= structId  +"-*-researchers", body=scope_param)
        entity = res['hits']['hits'][0]['_source']

        index = structId + '-' + entity['labHalId'] + '-researchers'


    elif type == "lab":
        scope_param = {
            "query": {
                "match": {
                    "halStructId": id
                }
            }
        }

        index = '*-laboratories'

        res = es.search(index=structId +"*-laboratories", body=scope_param)
        entity = res['hits']['hits'][0]['_source']

        index = structId + '-' + id  + 'laboratories'
    # /

    if request.method == 'POST':
        toInvalidate = request.POST.get("toInvalidate", "").split(",")
        for conceptId in toInvalidate:
            #to-do : désactiver les concepts
            for children in entity['concepts']['children']:
                if children['id'] == conceptId:
                    children['state'] = 'invalidated'
                if 'children' in children:
                    for children1 in children['children']:
                        if children1['id'] == conceptId:
                            if len(children['children']) == 1:
                                children['state'] = 'invalidated'
                            children1['state'] = 'invalidated'
                        if 'children' in children1:
                            for children2 in children1['children']:
                                if children2['id'] == conceptId:
                                    if len(children['children']) == 1:
                                        children['state'] = 'invalidated'
                                    if len(children1['children']) == 1:
                                        children1['state'] = 'invalidated'
                                    children2['state'] = 'invalidated'


        es.update(index=index, refresh='wait_for', id=entity['ldapId'],
                  body={"doc": {"concepts": entity['concepts']}})

    return redirect('/check/?type=' + type + '&id=' + id  + '&from=' + dateFrom + '&to=' + dateTo + '&data=' + data)



def validateCredentials(request):

    # Get parameters
    if 'type' in request.GET:
        type = request.GET['type']
    else:
        return redirect('unknown')
    if 'id' in request.GET:
        id = request.GET['id']
    else:
        return redirect('unknown')
    if 'data' in request.GET:
        data = request.GET['data']
    else:
        data = -1
    if 'from' in request.GET:
        dateFrom = request.GET['from']
    if 'to' in request.GET:
        dateTo = request.GET['to']

    # Connect to DB
    es = esConnector()

    if request.method == 'POST':

        if type == "rsr":
            idRef = request.POST.get("f_IdRef")
            orcId = request.POST.get("f_orcId")

            scope_param = {
                "query": {
                    "match": {
                        "_id": id
                    }
                }
            }

            res = es.search(index=structId +"*-researchers", body=scope_param)
            entity = res['hits']['hits'][0]['_source']

            print(structId + "-" + entity['labHalId'] + '-researchers')

            es.update(index=structId + "-" + entity['labHalId'] + '-researchers', refresh='wait_for', id=id,
                      body={"doc": {"idRef": idRef, "orcId": orcId}})

        if type == "lab":
            halStructId = request.POST.get("f_halStructId")
            rsnr = request.POST.get("f_rsnr")
            idRef = request.POST.get("f_IdRef")

            es.update(index=structId + "-" +  id +  "-laboratories", refresh='wait_for', id=id,
                      body={"doc": {"halStructId": halStructId, "rsnr": rsnr, "idRef": idRef}})

    return redirect('/check/?type=' + type + '&id=' + id  + '&from=' + dateFrom + '&to=' + dateTo + '&data=' + data)


def validateGuidingKeywords(request):
    # Get parameters
    if 'type' in request.GET:
        type = request.GET['type']
    else:
        return redirect('unknown')
    if 'id' in request.GET:
        id = request.GET['id']
    else:
        return redirect('unknown')
    if 'data' in request.GET:
        data = request.GET['data']
    else:
        data = -1
    if 'from' in request.GET:
        dateFrom = request.GET['from']
    if 'to' in request.GET:
        dateTo = request.GET['to']

    # Connect to DB
    es = esConnector()

    if request.method == 'POST':

        guidingKeywords = request.POST.get("f_guidingKeywords").split(";")

        if type == "rsr":

            scope_param = {
                "query": {
                    "match": {
                        "_id": id
                    }
                }
            }

            res = es.search(index=structId +"*-researchers", body=scope_param)
            entity = res['hits']['hits'][0]['_source']

            es.update(index=structId + "-" +  entity['labHalId'] +  "-researchers", refresh='wait_for', id=id,
                  body={"doc": {"guidingKeywords": guidingKeywords}})

        if type == "lab":
            es.update(index=structId + "-" +  str(id)  +  "-laboratories", refresh='wait_for', id=id,
                      body={"doc": {"guidingKeywords": guidingKeywords}})

    return redirect('/check/?type=' + type + '&id=' + id  + '&from=' + dateFrom + '&to=' + dateTo + '&data=' + data)

def faq(request):
    return render(request, 'faq.html')

def ressources(request):
    return render(request, 'ressources.html')

def tools(request):
    return render(request, 'tools.html')

def presentation(request):
    return render(request, 'presentation.html')

def wordcloud(request):
    # Get parameters
    if 'type' in request.GET:
        type = request.GET['type']
    else:
        return redirect('unknown')
    if 'id' in request.GET:
        id = request.GET['id']
    else:
        return redirect('unknown')
    # /

    # Connect to DB
    es = esConnector()

    # Get scope informations
    if type == "rsr":
        scope_param = {
            "query": {
                "match": {
                    "_id": id
                }
            }
        }

        key = 'halId_s'
        ext_key = "harvested_from_ids"

        res = es.search(index=structId +"*-researchers", body=scope_param)
        entity = res['hits']['hits'][0]['_source']

    elif type == "lab":
        scope_param = {
            "query": {
                "match": {
                    "halStructId": id
                }
            }
        }

        key = "halStructId"
        ext_key = "labStructId_i"

        res = es.search(index=structId +"*-laboratories", body=scope_param)
        entity = res['hits']['hits'][0]['_source']
    # /

    hasToConfirm = False

    if type == "rsr":
        hasToConfirm_param = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "match_phrase": {
                                "harvested_from_ids": entity['halId_s']
                            }
                        },
                        {
                            "match": {
                                "validated": False
                            }
                        }
                    ]
                }
            }
        }

    if type == "lab":
        hasToConfirm_param = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "match_phrase": {
                                "harvested_from_ids": entity['halStructId']
                            }
                        },
                        {
                            "match": {
                                "validated": False
                            }
                        }
                    ]
                }
            }
        }

    if es.count(index= structId + "*-documents", body=hasToConfirm_param)['count'] > 0:
        hasToConfirm = True

    # Get first submittedDate_tdate date
    if type == "rsr":
        start_date_param = {
            "size": 1,
            "sort": [
                {"submittedDate_tdate": {"order": "asc"}}
            ],
            "query": {
                "match_phrase": {"harvested_from_ids": entity['halId_s']}
            }
        }
    elif type == "lab":
        start_date_param = {
            "size": 1,
            "sort": [
                {"submittedDate_tdate": {"order": "asc"}}
            ],
            "query": {
                "match_phrase": {"harvested_from_ids": entity['halStructId']}
            }
        }

    res = es.search(index=structId +"*-documents", body=start_date_param)
    start_date = res['hits']['hits'][0]['_source']['submittedDate_tdate']
    # /

    # Get parameters
    if 'from' in request.GET:
        dateFrom = request.GET['from']
    else:
        dateFrom = start_date[0:4] + '-01-01'

    if 'to' in request.GET:
        dateTo = request.GET['to']
    else:
        dateTo = datetime.today().strftime('%Y-%m-%d')
    # /

    return render(request, 'wordcloud.html', {'type': type, 'id': id, 'from': dateFrom, 'to': dateTo,
                                              'entity': entity,
                                              'hasToConfirm': hasToConfirm,
                                              'filter': ext_key + ':"' + entity[key] + '" AND validated:true',
                                              'startDate': start_date,
                                              'timeRange': "from:'" + dateFrom + "',to:'" + dateTo + "'"})

def publicationboard(request):
    # Get parameters
    if 'type' in request.GET:
        type = request.GET['type']
    else:
        return redirect('unknown')
    if 'id' in request.GET:
        id = request.GET['id']
    else:
        return redirect('unknown')
    # /

    # Connect to DB
    es = esConnector()

    # Get scope informations
    if type == "rsr":
        scope_param = {
            "query": {
                "match": {
                    "_id": id
                }
            }
        }

        key = 'halId_s'
        ext_key = "harvested_from_ids"

        res = es.search(index=structId +"*-researchers", body=scope_param)
        entity = res['hits']['hits'][0]['_source']

    elif type == "lab":
        scope_param = {
            "query": {
                "match": {
                    "halStructId": id
                }
            }
        }

        key = "halStructId"
        ext_key = "harvested_from_ids"

        res = es.search(index=structId +"*-laboratories", body=scope_param)
        entity = res['hits']['hits'][0]['_source']
    # /

    hasToConfirm = False

    if type == "rsr":
        hasToConfirm_param = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "match_phrase": {
                                "harvested_from_ids": entity['halId_s']
                            }
                        },
                        {
                            "match": {
                                "validated": False
                            }
                        }
                    ]
                }
            }
        }

    if type == "lab":
        hasToConfirm_param = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "match_phrase": {
                                "harvested_from_ids": entity['halStructId']
                            }
                        },
                        {
                            "match": {
                                "validated": False
                            }
                        }
                    ]
                }
            }
        }

    if es.count(index="*-documents", body=hasToConfirm_param)['count'] > 0:
        hasToConfirm = True

    # Get first submittedDate_tdate date
    if type == "rsr":
        start_date_param = {
            "size": 1,
            "sort": [
                {"submittedDate_tdate": {"order": "asc"}}
            ],
            "query": {
                "match_phrase": {"harvested_from_ids": entity['halId_s']}
            }
        }
    elif type == "lab":
        start_date_param = {
            "size": 1,
            "sort": [
                {"submittedDate_tdate": {"order": "asc"}}
            ],
            "query": {
                "match_phrase": {"harvested_from_ids": entity['halStructId']}
            }
        }

    res = es.search(index=structId +"*-documents", body=start_date_param)
    start_date = res['hits']['hits'][0]['_source']['submittedDate_tdate']
    # /

    # Get parameters
    if 'from' in request.GET:
        dateFrom = request.GET['from']
    else:
        dateFrom = start_date[0:4] + '-01-01'

    if 'to' in request.GET:
        dateTo = request.GET['to']
    else:
        dateTo = datetime.today().strftime('%Y-%m-%d')
    # /

    return render(request, 'publicationboard.html', {'type': type, 'id': id, 'from': dateFrom, 'to': dateTo,
                                                     'entity': entity,
                                                     'hasToConfirm': hasToConfirm,
                                                     'filter': ext_key + ':"' + entity[key] + '" AND validated:true',
                                                     'startDate': start_date,
                                                     'timeRange': "from:'" + dateFrom + "',to:'" + dateTo + "'"})

def contact(request):
    if request.method == 'POST':
        f = ContactForm(request.POST)
        if f.is_valid():
            # send message to admin
            name = f.cleaned_data['nom']
            usermail=[f.cleaned_data['email']]
            subject = "Vous avez reçu une demande de {}:<{}>".format(name, usermail)



            message = "Objet: {}\n\nDate: {}\n\nMessage:\n\n {}".format(
                dict(f.purpose_choices).get(f.cleaned_data['objet']),
                datetime.now().isoformat(timespec='minutes'),
                f.cleaned_data['message']
            )

            mail_admins(subject, message, fail_silently=False, connection=None, html_message=None)

            # /

            # send confirmation message to user

            conf_subject ="Confirmation de reception du ticket:{}".format(dict(f.purpose_choices).get(f.cleaned_data['objet'])
                                                                          )

            conf_message="Bonjour {},\nCeci est un message automatisé pour vous informer que votre ticket a bien été reçu.\n\n{}".format(name,message)

            send_mail(conf_subject,conf_message,'testsovis@gmail.com',usermail,fail_silently = False)
            # /

            messages.add_message(request, messages.INFO, 'Votre message a bien été envoyé.')
            f = ContactForm()

            return render(request, 'contact.html', {'form': f})

    else:
        f = ContactForm()

    return render(request, 'contact.html', {'form': f})
