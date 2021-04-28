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
from ssl import create_default_context
from elasticsearch.connection import create_ssl_context
from uniauth.decorators import login_required

Mode = 'dev'

def esConnector(mode = Mode):
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
    return redirect('dashboard')


def unknown(request):
    return render(request, '404.html')

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

        count = es.count(index="documents", body=scope_param)['count']
        res = es.search(index="laboratories", body=scope_param, size=count)
        entities = res['hits']['hits']

    elif type == "rsr":

        if id == -1:
            scope_param = {
                "query": {
                    "match_all": {}
                }
            }

            count = es.count(index="researchers", body=scope_param)['count']

        else:
            scope_param = {
                "query": {
                    "match": {
                        "labHalId": id
                    }
                }
            }

            count = es.count(index="researchers", body=scope_param)['count']

        res = es.search(index="researchers", body=scope_param, size=count)
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
        ext_key = "authIdHal_s"

        res = es.search(index="researchers", body=scope_param)
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

        res = es.search(index="laboratories", body=scope_param)
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

    if es.count(index="documents", body=hasToConfirm_param)['count'] > 0:
        hasToConfirm = True

    # Get first submittedDate_tdate date
    if type == "rsr":
        start_date_param = {
            "size": 1,
            "sort": [
                {"submittedDate_tdate": {"order": "asc"}}
            ],
            "query": {
                "match_phrase": {"authIdHal_s": entity['halId_s']}
            }
        }
    elif type == "lab":
        start_date_param = {
            "size": 1,
            "sort": [
                {"submittedDate_tdate": {"order": "asc"}}
            ],
            "query": {
                "match_phrase": {"labStructId_i": entity['halStructId']}
            }
        }

    res = es.search(index="documents", body=start_date_param)
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
        ext_key = "authIdHal_s"

        res = es.search(index="researchers", body=scope_param)
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

        res = es.search(index="laboratories", body=scope_param)
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
                "match_phrase": {"authIdHal_s": entity['halId_s']}
            }
        }
    elif type == "lab":
        start_date_param = {
            "size": 1,
            "sort": [
                {"submittedDate_tdate": {"order": "asc"}}
            ],
            "query": {
                "match_phrase": {"labStructId_i": entity['halStructId']}
            }
        }

    res = es.search(index="documents", body=start_date_param)
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
                                "authIdHal_s": entity['halId_s']
                            }
                        },
                        {
                            "match": {
                                "validated": True
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
                                "labStructId_i": entity['halStructId']
                            }
                        },
                        {
                            "match": {
                                "validated": True
                            }
                        }
                    ]
                }
            }
        }

    if es.count(index="documents", body=hasToConfirm_param)['count'] > 0:
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

    count = es.count(index="documents", body=ref_param)['count']

    references = es.search(index="documents", body=ref_param, size=count)

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
        ext_key = "authIdHal_s"

        res = es.search(index="researchers", body=scope_param)
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

        res = es.search(index="laboratories", body=scope_param)
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
                "match_phrase": {"authIdHal_s": entity['halId_s']}
            }
        }
    elif type == "lab":
        start_date_param = {
            "size": 1,
            "sort": [
                {"submittedDate_tdate": {"order": "asc"}}
            ],
            "query": {
                "match_phrase": {"labStructId_i": entity['halStructId']}
            }
        }

    res = es.search(index="documents", body=start_date_param)

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
        count = es.count(index="researchers", body=rsr_param)['count']

        rsrs = es.search(index="researchers", body=rsr_param, size=count)

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

        count = es.count(index="documents", body=ref_param)['count']

        references = es.search(index="documents", body=ref_param, size=count)

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

    min_date = es.search(index="documents", body=date_param, size=0)['aggregations']['min_date']['value_as_string']

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

        if index == 'documents':
            search_param = {
                "query":{"bool":{"must": [{"query_string": {"query": search}}],"filter":[{"match":{"validated":"true"}}]}}
            }
        elif index=='researchers':
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
        ext_key = "authIdHal_s"

        res = es.search(index="researchers", body=scope_param)
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

        res = es.search(index="laboratories", body=scope_param)
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

    if es.count(index="documents", body=hasToConfirm_param)['count'] > 0:
        hasToConfirm = True

    # Get first submittedDate_tdate date
    if type == "rsr":
        start_date_param = {
            "size": 1,
            "sort": [
                {"submittedDate_tdate": {"order": "asc"}}
            ],
            "query": {
                "match_phrase": {"authIdHal_s": entity['halId_s']}
            }
        }
    elif type == "lab":
        start_date_param = {
            "size": 1,
            "sort": [
                {"submittedDate_tdate": {"order": "asc"}}
            ],
            "query": {
                "match_phrase": {"labStructId_i": entity['halStructId']}
            }
        }

    res = es.search(index="documents", body=start_date_param)
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

    if request.method == 'POST':
        toValidate = request.POST.get("toValidate", "").split(",")
        for docid in toValidate:
            es.update(index="documents", refresh='wait_for', id=docid,
                      body={"doc": {"validated": True}})

    return redirect('/check/?type=' + type + '&id=' + id + '&from=' + dateFrom + '&to=' + dateTo + '&data=' + data)


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

        key = 'halId_s'
        ext_key = "authIdHal_s"

        index = 'researchers'

        res = es.search(index="researchers", body=scope_param)
        entity = res['hits']['hits'][0]['_source']

    elif type == "lab":
        scope_param = {
            "query": {
                "match": {
                    "halStructId": id
                }
            }
        }

        index = 'laboratories'

        key = "halStructId"
        ext_key = "labStructId_i"

        res = es.search(index="laboratories", body=scope_param)
        entity = res['hits']['hits'][0]['_source']
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

    return redirect('/check/?type=' + type + '&id=' + id + '&from=' + dateFrom + '&to=' + dateTo + '&data=' + data)



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
            halId_s = request.POST.get("f_halId_s")
            halId_i = request.POST.get("f_halId_i")
            idRef = request.POST.get("f_IdRef")
            orcId = request.POST.get("f_orcId")

            es.update(index="researchers", refresh='wait_for', id=id,
                      body={"doc": {"halId_s": halId_s, "halId_i": halId_i, "idRef": idRef, "orcId": orcId}})

        if type == "lab":
            halStructId = request.POST.get("f_halStructId")
            rsnr = request.POST.get("f_rsnr")
            idRef = request.POST.get("f_IdRef")

            es.update(index="laboratories", refresh='wait_for', id=id,
                      body={"doc": {"halStructId": halStructId, "rsnr": rsnr, "idRef": idRef}})

    return redirect('/check/?type=' + type + '&id=' + id + '&from=' + dateFrom + '&to=' + dateTo + '&data=' + data)


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
            es.update(index="researchers", refresh='wait_for', id=id,
                      body={"doc": {"guidingKeywords": guidingKeywords}})

        if type == "lab":
            es.update(index="laboratories", refresh='wait_for', id=id,
                      body={"doc": {"guidingKeywords": guidingKeywords}})

    return redirect('/check/?type=' + type + '&id=' + id + '&from=' + dateFrom + '&to=' + dateTo + '&data=' + data)

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
        ext_key = "authIdHal_s"

        res = es.search(index="researchers", body=scope_param)
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

        res = es.search(index="laboratories", body=scope_param)
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

    if es.count(index="documents", body=hasToConfirm_param)['count'] > 0:
        hasToConfirm = True

    # Get first submittedDate_tdate date
    if type == "rsr":
        start_date_param = {
            "size": 1,
            "sort": [
                {"submittedDate_tdate": {"order": "asc"}}
            ],
            "query": {
                "match_phrase": {"authIdHal_s": entity['halId_s']}
            }
        }
    elif type == "lab":
        start_date_param = {
            "size": 1,
            "sort": [
                {"submittedDate_tdate": {"order": "asc"}}
            ],
            "query": {
                "match_phrase": {"labStructId_i": entity['halStructId']}
            }
        }

    res = es.search(index="documents", body=start_date_param)
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
        ext_key = "authIdHal_s"

        res = es.search(index="researchers", body=scope_param)
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

        res = es.search(index="laboratories", body=scope_param)
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

    if es.count(index="documents", body=hasToConfirm_param)['count'] > 0:
        hasToConfirm = True

    # Get first submittedDate_tdate date
    if type == "rsr":
        start_date_param = {
            "size": 1,
            "sort": [
                {"submittedDate_tdate": {"order": "asc"}}
            ],
            "query": {
                "match_phrase": {"authIdHal_s": entity['halId_s']}
            }
        }
    elif type == "lab":
        start_date_param = {
            "size": 1,
            "sort": [
                {"submittedDate_tdate": {"order": "asc"}}
            ],
            "query": {
                "match_phrase": {"labStructId_i": entity['halStructId']}
            }
        }

    res = es.search(index="documents", body=start_date_param)
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