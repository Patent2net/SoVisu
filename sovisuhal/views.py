import json
from datetime import datetime

from django.contrib import messages
from django.core.mail import mail_admins, mail_managers, send_mail
from django.shortcuts import render, redirect
from django.views.decorators.clickjacking import xframe_options_exempt
from . import forms, viewsActions
from .forms import ContactForm

from urllib.parse import urlencode
from django.urls import reverse

from .libs import utils, halConcepts, esActions

# from celery.result import AsyncResult

# from ssl import create_default_context
# from elasticsearch.connection import create_ssl_context
# from uniauth.decorators import login_required


# def get_progress(request, task_id):
#     result = AsyncResult(task_id)
#     response_data = {
#         'state': result.state,
#         'details': result.info,
#     }
#     return HttpResponse(json.dumps(response_data), content_type='application/json')


# Pages
def unknown(request):
    return render(request, '404.html')


def index(request):
    # Get parameters
    if 'type' in request.GET:
        type = request.GET['type']
    else:
        type = -1
    if 'id' in request.GET:
        id = request.GET['id']
    else:
        id = -1
    # /

    # Connect to DB
    es = esActions.es_connector()

    if type == "lab":
        scope_param = esActions.scope_all()

        count = es.count(index=viewsActions.structId + "*-laboratories", body=scope_param)['count']
        res = es.search(index=viewsActions.structId + "*-laboratories", body=scope_param, size=count)
        entities = res['hits']['hits']

    elif type == "rsr":

        if id == -1:
            scope_param = esActions.scope_all()

            count = es.count(index=viewsActions.structId + "*-researchers", body=scope_param)['count']
            res = es.search(index=viewsActions.structId + "*-researchers", body=scope_param, size=count)
        else:

            field = "labHalId"
            scope_param = esActions.scope_p(field, id)

            count = es.count(index=viewsActions.structId + "-" + id + "-researchers", body=scope_param)['count']

            res = es.search(index=viewsActions.structId + "-" + id + "-researchers", body=scope_param, size=count)
        entities = res['hits']['hits']
    cleaned_entities = []

    for entity in entities:
        cleaned_entities.append(entity['_source'])

    if type == "lab":
        cleaned_entities = sorted(cleaned_entities, key=lambda k: k['acronym'])
    elif type == "rsr":
        cleaned_entities = sorted(cleaned_entities, key=lambda k: k['lastName'])

    # /

    return render(request, 'index.html', {'entities': cleaned_entities, 'type': type})


def dashboard(request):
    # Get parameters
    if 'type' in request.GET and 'id' in request.GET:
        type = request.GET['type']
        id = request.GET['id']

    elif request.user.is_authenticated:
        id = request.user.get_username()
        id = id.replace(viewsActions.patternCas, '').lower()
        if id == 'adminlab':
            type = "lab"
            base_url = reverse('index')
            query_string = urlencode({'type': type})
            url = '{}?{}'.format(base_url, query_string)
            return redirect(url)
        if id == "invitamu":
            type = "rsr"
            base_url = reverse('index')
            query_string = urlencode({'type': type})
            url = '{}?{}'.format(base_url, query_string)
            return redirect(url)

        elif not id == 'adminlab' and not id == 'visiteur':
            type = "rsr"
            base_url = reverse('dashboard')
            query_string = urlencode({'type': type, 'id': id})
            url = '{}?{}'.format(base_url, query_string)
            return redirect(url)
        else:
            return redirect('unknown')
    else:
        return redirect('unknown')

    # /
    # Connect to DB
    es = esActions.es_connector()

    # Get scope informations
    if type == "rsr":
        field = "_id"
        key = 'halId_s'
        search_id = "*"
        index_pattern = "-researchers"

    elif type == "lab":
        field = "halStructId"
        key = "halStructId"
        search_id = id
        index_pattern = "-laboratories"

    ext_key = "harvested_from_ids"

    scope_param = esActions.scope_p(field, id)

    res = es.search(index=viewsActions.structId + "-" + search_id + index_pattern,
                    body=scope_param)  # on pointe sur index générique car pas de LabHalId ?

    try:
        entity = res['hits']['hits'][0]['_source']
    except:
        return redirect('unknown')
    # /

    hasToConfirm = False

    validate = False
    if type == "rsr":
        field = "authIdHal_s"
        hasToConfirm_param = esActions.confirm_p(field, entity['halId_s'], validate)

        # devrait scindé en deux ex.count qui diffèrent selon lab ou rsr dans les if précédent
        #  par ex pour == if type == "rsr": : es.count(index=struct  + "-" + entity['halStructId']+"-"researchers-" +
        #  entity["ldapId"] +"-documents", body=hasToConfirm_param)['count'] > 0:

    if type == "lab":
        field = "labStructId_i"
        hasToConfirm_param = esActions.confirm_p(field, entity['halStructId'], validate)

    if es.count(index=viewsActions.structId + "*-documents", body=hasToConfirm_param)[
        'count'] > 0:  # devrait scindé en deux ex.count qui diffèrent selon lab ou rsr dans les if précédent
        #  par ex pour == if type == "lab": : es.count(index=struct  + "-" + entity['halStructId']+"-documents", body=hasToConfirm_param)['count'] > 0:
        hasToConfirm = True

    # Get first submittedDate_tdate date
    if type == "rsr":
        try:
            start_date_param = esActions.date_all()

            res = es.search(
                index=viewsActions.structId + '-' + entity['labHalId'] + "-researchers-" + entity['ldapId'] + "-documents",
                body=start_date_param)
        except:
            start_date_param.pop("sort")
            res = es.search(
                index=viewsActions.structId + '-' + entity['labHalId'] + "-researchers-" + entity['ldapId'] + "-documents",
                body=start_date_param)

        filtrelab = ''
    elif type == "lab":
        field = "harvested_from_ids"
        start_date_param = esActions.date_p(field, entity['halStructId'])

        res = es.search(index=viewsActions.structId + '-' + id + "-laboratories-documents", body=start_date_param)

        filtrelab = 'harvested_from_ids: "' + id + '"'
    try:
        start_date = res['hits']['hits'][0]['_source']['submittedDate_tdate']
    except:
        start_date = "2000"
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
                                              'ext_key': ext_key,
                                              'key': entity[key],
                                              'filter': ext_key + ':"' + entity[key] + '" AND validated:true',
                                              'filterlab': filtrelab,
                                              'startDate': start_date,
                                              'timeRange': "from:'" + dateFrom + "',to:'" + dateTo + "'"})


def references(request):
    # Get parameters
    if 'type' in request.GET and 'id' in request.GET:
        type = request.GET['type']
        id = request.GET['id']

    elif request.user.is_authenticated:
        id = request.user.get_username()
        id = id.replace(viewsActions.patternCas, '').lower()
        if id == 'adminlab':
            type = "lab"
            base_url = reverse('index')
            query_string = urlencode({'type': type})
            url = '{}?{}'.format(base_url, query_string)
            return redirect(url)
        if id == "invitamu":
            type = "rsr"
            base_url = reverse('index')
            query_string = urlencode({'type': type})
            url = '{}?{}'.format(base_url, query_string)
            return redirect(url)

        elif not id == 'adminlab' and not id == 'visiteur':
            type = "rsr"
            base_url = reverse('references')
            default_filter = 'uncomplete'
            query_string = urlencode({'type': type, 'id': id, 'filter': default_filter})
            url = '{}?{}'.format(base_url, query_string)
            return redirect(url)

        else:
            return redirect('unknown')
    else:
        return redirect('unknown')

    if 'filter' in request.GET:
        filter = request.GET['filter']
    else:
        filter = -1

    # /
    # Connect to DB
    es = esActions.es_connector()

    # Get scope informations
    if type == "rsr":
        field = "_id"
        key = 'halId_s'
        search_id = "*"
        index_pattern = "-researchers"

    elif type == "lab":
        field = "halStructId"
        key = "halStructId"
        search_id = id
        index_pattern = "-laboratories"

    ext_key = "harvested_from_ids"

    scope_param = esActions.scope_p(field, id)

    res = es.search(index=viewsActions.structId + "-" + search_id + index_pattern,
                    body=scope_param)  # on pointe sur index générique car pas de LabHalId ?

    try:
        entity = res['hits']['hits'][0]['_source']
    except:
        return redirect('unknown')
    # /

    # Get first submittedDate_tdate date
    field = "harvested_from_ids"

    if type == "rsr":
        start_date_param = esActions.date_p(field, entity['halId_s'])

        res = es.search(index=viewsActions.structId + "-" + entity['labHalId'] + "-researchers-" + entity['ldapId'] + "-documents",
                        body=start_date_param)  # labHalId est-il là ?
    elif type == "lab":
        start_date_param = esActions.date_p(field, entity['halStructId'])

        res = es.search(index=viewsActions.structId + "-" + id + "-laboratories-documents", body=start_date_param)

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
    field = "harvested_from_ids"
    validate = False
    if type == "rsr":

        hasToConfirm_param = esActions.confirm_p(field, entity['halId_s'], validate)

        if es.count(index=viewsActions.structId + "-" + entity['labHalId'] + "-researchers-" + entity['ldapId'] + "-documents",
                    body=hasToConfirm_param)['count'] > 0:
            hasToConfirm = True
    if type == "lab":

        hasToConfirm_param = esActions.confirm_p(field, entity['halStructId'], validate)

        if es.count(index=viewsActions.structId + "-" + entity['halStructId'] + "-laboratories-documents", body=hasToConfirm_param)[
            'count'] > 0:
            hasToConfirm = True

    # Get references
    scope_bool_type = "filter"
    validate = True
    date_range_type = "submittedDate_tdate"
    ref_param = esActions.ref_p_filter(filter, scope_bool_type, ext_key, entity[key], validate, date_range_type,
                                       dateFrom,
                                       dateTo)

    if type == "rsr":  # I hope this is a focused search :-/
        count = es.count(index=viewsActions.structId + "-" + entity["labHalId"] + "-researchers-" + entity['ldapId'] + "-documents",
                         body=ref_param)['count']
        references = es.search(
            index=viewsActions.structId + "-" + entity["labHalId"] + "-researchers-" + entity['ldapId'] + "-documents",
            body=ref_param, size=count)

    if type == "lab":
        count = es.count(index=viewsActions.structId + "-" + entity["halStructId"] + "-laboratories-documents", body=ref_param)[
            'count']
        references = es.search(index=viewsActions.structId + "-" + entity["halStructId"] + "-laboratories-documents", body=ref_param,
                               size=count)

    references_cleaned = []

    for ref in references['hits']['hits']:
        references_cleaned.append(ref['_source'])
    # /
    print(references_cleaned)
    return render(request, 'references.html', {'filter': filter, 'type': type, 'id': id, 'from': dateFrom, 'to': dateTo,
                                               'entity': entity,
                                               'hasToConfirm': hasToConfirm,
                                               'references': references_cleaned, 'startDate': start_date,
                                               'timeRange': "from:'" + dateFrom + "',to:'" + dateTo + "'"})


def check(request):
    # Connect to DB

    if request.user.is_authenticated and request.user.get_username() == 'visiteur':
        return redirect('unknown')

    es = esActions.es_connector()

    # Get parameters
    if 'type' in request.GET and 'id' in request.GET:
        type = request.GET['type']
        id = request.GET['id']

    elif request.user.is_authenticated:
        id = request.user.get_username()
        id = id.replace(viewsActions.patternCas, '').lower()
        if id == 'adminlab':
            type = "lab"
            base_url = reverse('index')
            query_string = urlencode({'type': type})
            url = '{}?{}'.format(base_url, query_string)
            return redirect(url)
        if id == "invitamu":
            type = "rsr"
            base_url = reverse('index')
            query_string = urlencode({'type': type})
            url = '{}?{}'.format(base_url, query_string)
            return redirect(url)

        elif not id == 'adminlab' and not id == 'visiteur':
            type = "rsr"
            default_data = "credentials"
            base_url = reverse('check')
            query_string = urlencode({'type': type, 'id': id, 'data': default_data})
            url = '{}?{}'.format(base_url, query_string)
            return redirect(url)

        else:
            return redirect('unknown')
    else:
        return redirect('unknown')

    if 'data' in request.GET:
        data = request.GET['data']
    else:
        data = -1
    # /
    if data == -1:
        return render(request, 'check.html', {'data': viewsActions.create,
                                              # 'type': type, 'id': id, 'from': dateFrom, 'to': dateTo,
                                              'form': forms.CreateCredentials(),

                                              }
                      )

    # Get scope informations
    if type == "rsr":
        field = "_id"
        key = 'halId_s'
        search_id = "*"
        index_pattern = "-researchers"

    elif type == "lab":
        field = "halStructId"
        key = "halStructId"
        search_id = id
        index_pattern = "-laboratories"

    ext_key = "harvested_from_ids"

    scope_param = esActions.scope_p(field, id)

    res = es.search(index=viewsActions.structId + "-" + search_id + index_pattern,
                    body=scope_param)  # on pointe sur index générique car pas de LabHalId ?

    try:
        entity = res['hits']['hits'][0]['_source']
    except:
        return redirect('unknown')
    # /

    # Get first submittedDate_tdate date
    field = "harvested_from_ids"
    if type == "rsr":
        start_date_param = esActions.date_p(field, entity['halId_s'])

        try:

            res = es.search(index=viewsActions.structId + "-" + entity['labHalId'] + "-researchers-" + id + "-documents",
                            body=start_date_param)
            start_date = res['hits']['hits'][0]['_source']['submittedDate_tdate']
        except:
            start_date_param.pop("sort")
            res = es.search(index=viewsActions.structId + "-" + entity['labHalId'] + "-researchers-" + id + "-documents",
                            body=start_date_param)
            start_date = "2000"
    elif type == "lab":
        start_date_param = esActions.date_p(field, entity['halStructId'])

        try:

            res = es.search(index=viewsActions.structId + "-" + entity['halStructId'] + "-laboratories-documents",
                            body=start_date_param)
            start_date = res['hits']['hits'][0]['_source']['submittedDate_tdate']
        except:
            start_date_param.pop("sort")
            res = es.search(index=viewsActions.structId + "-" + entity['halStructId'] + "-laboratories-documents",
                            body=start_date_param)
            start_date = "2000"

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
    validate = False
    if type == "rsr":
        field = "authIdHal_s"
        hasToConfirm_param = esActions.confirm_p(field, entity['halId_s'], validate)

        # devrait scindé en deux ex.count qui diffèrent selon lab ou rsr dans les if précédent
        #  par ex pour == if type == "rsr": : es.count(index=struct  + "-" + entity['halStructId']+"-"researchers-" + entity["ldapId"] +"-documents", body=hasToConfirm_param)['count'] > 0:

    if type == "lab":
        field = "labStructId_i"
        hasToConfirm_param = esActions.confirm_p(field, entity['halStructId'], validate)

    if es.count(index=viewsActions.structId + "*-documents", body=hasToConfirm_param)[
        'count'] > 0:  # devrait scindé en deux ex.count qui diffèrent selon lab ou rsr dans les if précédent
        #  par ex pour == if type == "lab": : es.count(index=struct  + "-" + entity['halStructId']+"-documents", body=hasToConfirm_param)['count'] > 0:
        hasToConfirm = True

    print(hasToConfirm)

    if data == "state":
        field = "labHalId"
        rsr_param = esActions.scope_p(field, id)

        count = es.count(index="*-researchers", body=rsr_param)['count']

        rsrs = es.search(index="*-researchers", body=rsr_param, size=count)

        rsrs_cleaned = []

        for result in rsrs['hits']['hits']:
            rsrs_cleaned.append(result['_source'])

        return render(request, 'check.html', {'data': data, 'type': type, 'id': id, 'from': dateFrom, 'to': dateTo,
                                              'entity': entity,
                                              'researchers': rsrs_cleaned,
                                              'startDate': start_date,
                                              'hasToConfirm': hasToConfirm,
                                              'timeRange': "from:'" + dateFrom + "',to:'" + dateTo + "'"})

    if data == "-1" or data == "credentials":

        if type == "rsr":
            orcId = ''
            if 'orcId' in entity:
                orcId = entity['orcId']
            if 'orcId' in request.GET:
                orcId = request.GET['orcId']
            function = 0
            if 'function' in entity:
                function = entity['function']

            return render(request, 'check.html', {'data': data, 'type': type, 'id': id, 'from': dateFrom, 'to': dateTo,
                                                  'entity': entity, 'extIds': ['a', 'b', 'c'],
                                                  'form': forms.validCredentials(halId_s=entity['halId_s'],
                                                                                 idRef=entity['idRef'], orcId=orcId,
                                                                                 function=function),
                                                  'startDate': start_date,
                                                  'hasToConfirm': hasToConfirm,
                                                  'timeRange': "from:'" + dateFrom + "',to:'" + dateTo + "'"})

        if type == "lab":
            return render(request, 'check.html', {'data': data, 'type': type, 'id': id, 'from': dateFrom, 'to': dateTo,
                                                  'entity': entity,
                                                  'form': forms.validLabCredentials(halStructId=entity['halStructId'],
                                                                                    rsnr=entity['rsnr'],
                                                                                    idRef=entity['idRef']),
                                                  'startDate': start_date,
                                                  'hasToConfirm': hasToConfirm,
                                                  'timeRange': "from:'" + dateFrom + "',to:'" + dateTo + "'"})

    elif data == "research-description":

        if 'research_summary' not in entity:
            research_summary = ''
        else:
            research_summary = entity['research_summary']

        if 'research_projectsAndFundings' not in entity:
            research_projectsAndFundings = ''
        else:
            research_projectsAndFundings = entity['research_projectsAndFundings']

        if 'research_projectsInProgress' not in entity:
            research_projectsInProgress = ''
        else:
            research_projectsInProgress = entity['research_projectsInProgress']

        return render(request, 'check.html', {'data': data, 'type': type, 'id': id, 'from': dateFrom, 'to': dateTo,
                                              'entity': entity, 'extIds': ['a', 'b', 'c'],
                                              'form': forms.setResearchDescription(research_summary=research_summary,
                                                                                   research_projectsInProgress=research_projectsInProgress,
                                                                                   research_projectsAndFundings=research_projectsAndFundings),
                                              'startDate': start_date,
                                              'research_summary': research_summary,
                                              'research_projectsInProgress': research_projectsInProgress,
                                              'research_projectsAndFundings': research_projectsAndFundings,
                                              'hasToConfirm': hasToConfirm,
                                              'timeRange': "from:'" + dateFrom + "',to:'" + dateTo + "'"})

    elif data == "expertise":
        if 'validation' in request.GET:
            validation = request.GET['validation']

        if validation == "1":
            validate = 'validated'
        elif validation == "0":
            validate = 'invalidated'
        else:
            return redirect('unknown')
        concepts = []
        if 'children' in entity['concepts']:
            for children in entity['concepts']['children']:
                if "state" in children.keys() and children['state'] == validate:
                    concepts.append(
                        {'id': children['id'], 'label_fr': children['label_fr'], 'state': validate})
                if 'children' in children:
                    for children1 in children['children']:
                        if "state" in children1.keys():
                            if children1['state'] == validate:
                                concepts.append(
                                    {'id': children1['id'], 'label_fr': children1['label_fr'], 'state': validate})
                            else:
                                print(children1)
                        if 'children' in children1:
                            for children2 in children1['children']:
                                if "state" in children2.keys() and children2['state'] == validate:
                                    concepts.append({'id': children2['id'], 'label_fr': children2['label_fr'],
                                                     'state': validate})

        return render(request, 'check.html', {'data': data, 'type': type, 'id': id, 'from': dateFrom, 'to': dateTo,
                                              'validation': validation,
                                              'entity': entity,
                                              'concepts': concepts,
                                              'startDate': start_date,
                                              'hasToConfirm': hasToConfirm,
                                              'timeRange': "from:'" + dateFrom + "',to:'" + dateTo + "'"})

    elif data == "guiding-keywords":
        return render(request, 'check.html', {'data': data, 'type': type, 'id': id, 'from': dateFrom, 'to': dateTo,
                                              'entity': entity,
                                              'form': forms.setGuidingKeywords(
                                                  guidingKeywords=entity['guidingKeywords']),
                                              'startDate': start_date,
                                              'hasToConfirm': hasToConfirm,
                                              'timeRange': "from:'" + dateFrom + "',to:'" + dateTo + "'"})

    elif data == "guiding-domains":

        domains = halConcepts.concepts()

        guidingDomains = []

        if 'guidingDomains' in entity:
            guidingDomains = entity['guidingDomains']

        return render(request, 'check.html', {'data': data, 'type': type, 'id': id, 'from': dateFrom, 'to': dateTo,
                                              'entity': entity,
                                              'domains': domains,
                                              'guidingDomains': guidingDomains,
                                              'startDate': start_date,
                                              'hasToConfirm': hasToConfirm,
                                              'timeRange': "from:'" + dateFrom + "',to:'" + dateTo + "'"})


    elif data == "references":
        if 'validation' in request.GET:
            validation = request.GET['validation']

        if validation == "1":
            validate = True
        elif validation == "0":
            validate = False
        else:
            return redirect('unknown')
        date_range_type = "submittedDate_tdate"
        scope_bool_type = "must"
        ref_param = esActions.ref_p(scope_bool_type, ext_key, entity[key], validate, date_range_type, dateFrom, dateTo)

        if type == "rsr":  # I hope this is a focused search :-/
            count = \
                es.count(index=viewsActions.structId + "-" + entity["labHalId"] + "-researchers-" + entity['ldapId'] + "-documents",
                         body=ref_param)['count']
            references = es.search(
                index=viewsActions.structId + "-" + entity["labHalId"] + "-researchers-" + entity['ldapId'] + "-documents",
                body=ref_param, size=count)

        if type == "lab":
            count = es.count(index=viewsActions.structId + "-" + entity["halStructId"] + "-laboratories-documents",
                             body=ref_param)['count']
            references = es.search(
                index=viewsActions.structId + "-" + entity["halStructId"] + "-laboratories-documents",
                body=ref_param, size=count)

        references_cleaned = []

        for ref in references['hits']['hits']:
            references_cleaned.append(ref['_source'])
        # /

        return render(request, 'check.html', {'data': data, 'type': type, 'id': id, 'from': dateFrom, 'to': dateTo,
                                              'validation': validation,
                                              'entity': entity,
                                              'hasToConfirm': hasToConfirm,
                                              'references': references_cleaned, 'startDate': start_date,
                                              'timeRange': "from:'" + dateFrom + "',to:'" + dateTo + "'"})

    else:
        return redirect('unknown')


def search(request):
    # Connect to DB
    es = esActions.es_connector()

    date_param = {
        "aggs": {
            "min_date": {"min": {"field": "submittedDate_tdate"}},
        }
    }

    min_date = es.search(index="*-documents", body=date_param, size=0)['aggregations']['min_date']['value_as_string']

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
        es = esActions.es_connector()

        index = request.POST.get("f_index")
        search = request.POST.get("f_search")

        if (viewsActions.structId + "-*-researchers-*-doc*") in index:  # == 'documents':
            search_param = {
                "query": {"bool": {"must": [{"query_string": {"query": search}}],
                                   "filter": [{"match": {"validated": "true"}}]}}
            }
        elif (viewsActions.structId + "-*-researchers") in index:  # =='researchers':
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
        messages.add_message(request, messages.INFO,
                             'Résultats de la recherche "{}" dans la collection "{}"'.format(search, index))
        return render(request, 'search.html', {'form': forms.search(val=search), 'count': p_res['count'],
                                               'timeRange': "from:'" + dateFrom + "',to:'" + dateTo + "'",
                                               'filter': search, 'index': index, 'search': search,
                                               'results': res_cleaned, 'from': dateFrom, 'to': dateTo,
                                               'startDate': min_date})

    return render(request, 'search.html',
                  {'form': forms.search(), 'from': dateFrom, 'to': dateTo, 'startDate': min_date, 'filter': ''})


@xframe_options_exempt
def terminology(request):

    # Get parameters
    if 'type' in request.GET and 'id' in request.GET:  # réutilisation de l'ancien système
        type = request.GET['type']
        id = request.GET['id']

    elif request.user.is_authenticated:  # si l'ancien système ne sais pas quoi faire
        id = request.user.get_username()  # check si l'utilisateur est log
        id = id.replace(viewsActions.patternCas, '').lower()
        if id == 'adminlab':  # si id adminlab on considère que son type par défaut est lab
            type = "lab"
            base_url = reverse('index')
            query_string = urlencode({'type': type})
            url = '{}?{}'.format(base_url, query_string)
            return redirect(url)
        if id == "invitamu":
            type = "rsr"
            base_url = reverse('index')
            query_string = urlencode({'type': type})
            url = '{}?{}'.format(base_url, query_string)
            return redirect(url)

        elif not id == 'adminlab' and not id == 'visiteur':  # si ce n'est pas adminlab ni un visiteur => c'est un chercheur
            type = "rsr"
            base_url = reverse('terminology')
            query_string = urlencode({'type': type, 'id': id})
            url = '{}?{}'.format(base_url, query_string)
            return redirect(url)

        else:  # sinon il est inconnu et doit aller dans l'index pour faire ses choix car on ne peut pas le suivre
            return redirect('unknown')
    else:  # retour à l'ancien système et redirect unknown si il n'est pas identifié et les type et id ne sont pas connu
        return redirect('unknown')

    if 'export' in request.GET:
        export = request.GET['export']
    else:
        export = False

    # /

    # Connect to DB
    es = esActions.es_connector()

    # Get scope informations
    if type == "rsr":
        field = "_id"
        search_id = "*"
        index_pattern = "-researchers"

    elif type == "lab":
        field = "halStructId"
        search_id = id
        index_pattern = "-laboratories"

    scope_param = esActions.scope_p(field, id)

    res = es.search(index=viewsActions.structId + "-" + search_id + index_pattern,
                    body=scope_param)  # on pointe sur index générique car pas de LabHalId ?

    try:
        entity = res['hits']['hits'][0]['_source']
    except:
        return redirect('unknown')
    # /

    hasToConfirm = False

    validate = False
    field = "harvested_from_ids"

    if type == "rsr":
        hasToConfirm_param = esActions.confirm_p(field, entity['halId_s'], validate)

    if type == "lab":
        hasToConfirm_param = esActions.confirm_p(field, entity['halStructId'], validate)

    if es.count(index="*-documents", body=hasToConfirm_param)['count'] > 0:
        hasToConfirm = True

    # Get first submittedDate_tdate date
    field = "harvested_from_ids"

    if type == "rsr":
        start_date_param = esActions.date_p(field, entity['halId_s'])

    elif type == "lab":
        start_date_param = esActions.date_p(field, entity['halStructId'])

    res = es.search(index=viewsActions.structId + "-*-documents", body=start_date_param)
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
        entity['concepts'] = json.dumps(entity['concepts'])

    if type == "rsr":
        entity['concepts'] = json.dumps(entity['concepts'])

    entity['concepts'] = json.loads(entity['concepts'])

    if type == "rsr":

        print(entity['concepts'])

        if 'children' in list(entity['concepts']):
            for children in list(entity['concepts']['children']):
                if children['state'] == 'invalidated':
                    entity['concepts']['children'].remove(children)

                if 'children' in children:
                    for children1 in list(children['children']):
                        if children1['state'] == 'invalidated':
                            children['children'].remove(children1)

                        if 'children' in children1:
                            for children2 in list(children1['children']):
                                print(children2)
                                if children2['state'] == 'invalidated':
                                    children1['children'].remove(children2)

        print(entity['concepts'])

    if type == "lab":
        if 'children' in list(entity['concepts']) and children in list(entity['concepts']['children']):
            if 'researchers' in children:
                state = 'invalidated'
                for rsr in children['researchers']:
                    if 'state' in rsr.keys():
                        if rsr['state'] == 'validated':
                            state = None
                    else:
                        pass
                        # pas sûr de bien comprendre ce qu'il y a à faire là ^_^
                if state:
                    entity['concepts']['children'].remove(children)

            if 'children' in children:
                for children1 in list(children['children']):
                    if 'researchers' in children:
                        state = 'invalidated'
                        for rsr in children1['researchers']:
                            if 'state' in rsr.keys():
                                if rsr['state'] == 'validated':
                                    state = None
                            else:
                                # idem
                                pass
                        if state:
                            children['children'].remove(children1)

                    if 'children' in children1:
                        for children2 in list(children1['children']):
                            if 'researchers' in children:
                                state = 'invalidated'
                                for rsr in children2['researchers']:
                                    if 'state' in rsr.keys():
                                        if rsr['state'] == 'validated':
                                            state = None
                                    else:
                                        pass
                                    # idem ter
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


def faq(request):
    return render(request, 'faq.html')


def ressources(request):
    return render(request, 'ressources.html')


def tools(request):

    # Get parameters
    if 'type' in request.GET and 'id' in request.GET:
        type = request.GET['type']
        id = request.GET['id']

    elif request.user.is_authenticated:
        id = request.user.get_username()
        id = id.replace(viewsActions.patternCas, '').lower()
        if id == 'adminlab':
            type = "lab"
            base_url = reverse('index')
            query_string = urlencode({'type': type})
            url = '{}?{}'.format(base_url, query_string)
            return redirect(url)
        if id == "invitamu":
            type = "rsr"
            base_url = reverse('index')
            query_string = urlencode({'type': type})
            url = '{}?{}'.format(base_url, query_string)
            return redirect(url)

        elif not id == 'adminlab' and not id == 'visiteur':
            type = "rsr"
            base_url = reverse('dashboard')
            query_string = urlencode({'type': type, 'id': id})
            url = '{}?{}'.format(base_url, query_string)
            return redirect(url)
        else:
            return redirect('unknown')
    else:
        return redirect('unknown')

    # /
    # Connect to DB
    es = esActions.es_connector()

    # Get scope informations
    if type == "lab":
        field = "halStructId"
        key = "halStructId"
        search_id = id
        index_pattern = "-laboratories"

    ext_key = "harvested_from_ids"

    scope_param = esActions.scope_p(field, id)

    res = es.search(index=viewsActions.structId + "-" + search_id + index_pattern,
                    body=scope_param)  # on pointe sur index générique car pas de LabHalId ?

    try:
        entity = res['hits']['hits'][0]['_source']
    except:
        return redirect('unknown')
    # /

    hasToConfirm = False

    validate = False
    if type == "lab":
        field = "labStructId_i"
        hasToConfirm_param = esActions.confirm_p(field, entity['halStructId'], validate)

    if es.count(index="*-documents", body=hasToConfirm_param)[
        'count'] > 0:  # devrait scindé en deux ex.count qui diffèrent selon lab ou rsr dans les if précédent
        #  par ex pour == if type == "lab": : es.count(index=struct  + "-" + entity['halStructId']+"-documents", body=hasToConfirm_param)['count'] > 0:
        hasToConfirm = True

    # Get first submittedDate_tdate date
    if type == "lab":
        field = "harvested_from_ids"
        start_date_param = esActions.date_p(field, entity['halStructId'])

        res = es.search(index=viewsActions.structId + '-' + id + "-laboratories-documents", body=start_date_param)

    try:
        start_date = res['hits']['hits'][0]['_source']['submittedDate_tdate']
    except:
        start_date = "2000"
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

    if 'data' in request.GET:
        data = request.GET['data']
    else:
        data = "hceres"

    if (data == "hceres" or data == -1):
        return render(request, 'tools.html', {'data': data, 'type': type, 'id': id, 'from': dateFrom, 'to': dateTo,
                                              'entity': entity,
                                              'hasToConfirm': hasToConfirm,
                                              'ext_key': ext_key,
                                              'key': entity[key],
                                              'startDate': start_date,
                                              'timeRange': "from:'" + dateFrom + "',to:'" + dateTo + "'"})


def useful_links(request):
    return render(request, 'useful_links.html')


def presentation(request):
    return render(request, 'presentation.html')


def wordcloud(request):
    # Get parameters
    if 'type' in request.GET and 'id' in request.GET:
        type = request.GET['type']
        id = request.GET['id']

    elif request.user.is_authenticated:
        id = request.user.get_username()
        id = id.replace(viewsActions.patternCas, '')
        if id == 'adminlab':
            type = "lab"
            base_url = reverse('index')
            query_string = urlencode({'type': type})
            url = '{}?{}'.format(base_url, query_string)
            return redirect(url)
        if id == "invitamu":
            type = "rsr"
            base_url = reverse('index')
            query_string = urlencode({'type': type})
            url = '{}?{}'.format(base_url, query_string)
            return redirect(url)

        elif not id == 'adminlab' and not id == 'visiteur':
            type = "rsr"
            base_url = reverse('wordcloud')
            query_string = urlencode({'type': type, 'id': id})
            url = '{}?{}'.format(base_url, query_string)
            return redirect(url)
        else:
            return redirect('unknown')
    else:
        return redirect('unknown')

    # /

    # Connect to DB
    es = esActions.es_connector()

    # Get scope informations
    if type == "rsr":
        field = "_id"
        key = 'halId_s'
        search_id = "*"
        index_pattern = "-researchers"

    elif type == "lab":
        field = "halStructId"
        key = "halStructId"
        search_id = id
        index_pattern = "-laboratories"

    ext_key = "harvested_from_ids"

    scope_param = esActions.scope_p(field, id)

    res = es.search(index=viewsActions.structId + "-" + search_id + index_pattern,
                    body=scope_param)  # on pointe sur index générique car pas de LabHalId ?

    try:
        entity = res['hits']['hits'][0]['_source']
    except:
        return redirect('unknown')
    # /

    hasToConfirm = False

    field = "harvested_from_ids"
    validate = False
    if type == "rsr":
        hasToConfirm_param = esActions.confirm_p(field, entity['halId_s'], validate)

    if type == "lab":
        hasToConfirm_param = esActions.confirm_p(field, entity['halStructId'], validate)

    if es.count(index=viewsActions.structId + "*-documents", body=hasToConfirm_param)['count'] > 0:
        hasToConfirm = True

    # Get first submittedDate_tdate date
    field = "harvested_from_ids"

    if type == "rsr":
        start_date_param = esActions.date_p(field, entity['halId_s'])

    elif type == "lab":

        start_date_param = esActions.date_p(field, entity['halStructId'])

    res = es.search(index=viewsActions.structId + "*-documents", body=start_date_param)
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


def publication_board(request):
    # Get parameters
    if 'type' in request.GET and 'id' in request.GET:
        type = request.GET['type']
        id = request.GET['id']

    elif request.user.is_authenticated:
        id = request.user.get_username()
        id = id.replace(viewsActions.patternCas, '')
        if id == 'adminlab':
            type = "lab"
            base_url = reverse('index')
            query_string = urlencode({'type': type})
            url = '{}?{}'.format(base_url, query_string)
            return redirect(url)
        if id == "invitamu":
            type = "rsr"
            base_url = reverse('index')
            query_string = urlencode({'type': type})
            url = '{}?{}'.format(base_url, query_string)
            return redirect(url)

        elif not id == 'adminlab' and not id == 'visiteur':
            type = "rsr"
            base_url = reverse('publicationboard')
            query_string = urlencode({'type': type, 'id': id})
            url = '{}?{}'.format(base_url, query_string)
            return redirect(url)
        else:
            return redirect('unknown')
    else:
        return redirect('unknown')

    # /

    # Connect to DB
    es = esActions.es_connector()

    # Get scope informations
    if type == "rsr":
        field = "_id"
        search_id = "*"
        index_pattern = "-researchers"

    elif type == "lab":
        field = "halStructId"
        search_id = id
        index_pattern = "-laboratories"

    scope_param = esActions.scope_p(field, id)

    res = es.search(index=viewsActions.structId + "-" + search_id + index_pattern,
                    body=scope_param)  # on pointe sur index générique car pas de LabHalId ?

    try:
        entity = res['hits']['hits'][0]['_source']
    except:
        return redirect('unknown')
    # /

    hasToConfirm = False

    field = "harvested_from_ids"
    validate = False
    if type == "rsr":
        hasToConfirm_param = esActions.confirm_p(field, entity['halId_s'], validate)

    if type == "lab":
        hasToConfirm_param = esActions.confirm_p(field, entity['halStructId'], validate)

    if es.count(index="*-documents", body=hasToConfirm_param)['count'] > 0:
        hasToConfirm = True

    # Get first submittedDate_tdate date
    field = "harvested_from_ids"

    if type == "rsr":

        start_date_param = esActions.date_p(field, entity['halId_s'])

        res = es.search(index=viewsActions.structId + '-' + entity['labHalId'] + "-researchers-" + id + "-documents",
                        body=start_date_param)
        # Première visu : entrée de l'annuaire
        filtreA = 'labHalId.keyword:"' + entity["labHalId"] + '" AND ldapId.keyword :"' + id + '"'
        # Deuxième visu : données du labo
        filtreB = 'halStructId.keyword:"' + entity["labHalId"] + '"'  # + 'ldapId.keyword :"' + id + '"'
        # Troisième visu : données éditeurs et revues de l'individu et validées
        filtreC = "harvested_from_ids" + ':"' + entity["halId_s"] + '" AND validated:true'
    elif type == "lab":

        start_date_param = esActions.date_p(field, entity['halStructId'])

        # Première visu : entrée de l'annuaire
        filtreA = 'labHalId.keyword:"' + id + '"'  # entity["labHalId"] # + '" AND ldapId.keyword :"' + id
        # Deuxième visu : données du labo
        filtreB = 'halStructId.keyword:"' + entity[
            "halStructId"] + '"'  # entity["labHalId"]+ '"'#+ 'ldapId.keyword :"' + id + '"'
        # Troisième visu : données éditeurs et revues de l'individu et validées
        filtreC = "harvested_from_ids" + ':"' + entity["halStructId"]  # + '" AND validated:true'
        res = es.search(index=viewsActions.structId + '-' + entity['halStructId'] + '-' + "laboratories-documents*",
                        body=start_date_param)

    start_date = res['hits']['hits'][0]['_source']['submittedDate_tdate']
    # /

    # Get parameters
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
                                                     'filterA': filtreA,
                                                     # "harvested_from_ids" + ':"' + entity["labHalId"] + '" AND validated:true',
                                                     'filterB': filtreB,
                                                     # 'labHalId.keyword:"' + entity["labHalId"]+ '" AND ldapId.keyword :"' + id + '"',
                                                     'filterC': filtreC,
                                                     # 'labHalId.keyword:"' + entity["labHalId"]+ '" AND ldapId.keyword :"' + id + '"',
                                                     'startDate': start_date,
                                                     'timeRange': "from:'" + dateFrom + "',to:'" + dateTo + "'"})


def contact(request):
    if request.method == 'POST':
        f = ContactForm(request.POST)
        if f.is_valid():
            # create mail content
            name = f.cleaned_data['nom']
            usermail = [f.cleaned_data['email']]
            sujet = f.cleaned_data['sujet']
            subject = "{} : {}".format(dict(f.purpose_choices).get(f.cleaned_data['objet']), sujet)

            message = "Date: {}\n\nCatégorie: {}\n\nNom d'utilisateur: {}\n\nMail de contact: {}\n\nSujet: {}\n\nDescription:\n\n {}".format(
                datetime.now().isoformat(timespec='minutes'),
                dict(f.purpose_choices).get(f.cleaned_data['objet']),
                name,
                usermail[0],
                sujet,
                f.cleaned_data['message']
            )
            if f.cleaned_data['objet'] == 'tb':  # send mail to registered MANAGERS in settings.py
                mail_managers(subject, message, fail_silently=False, connection=None, html_message=None)
            else:  # send mail to registered ADMINS in settings.py
                mail_admins(subject, message, fail_silently=False, connection=None, html_message=None)

            # /

            # send confirmation message to user

            conf_subject = "Confirmation de reception :{}".format(
                dict(f.purpose_choices).get(f.cleaned_data['objet'])
            )

            conf_message = "Bonjour {},\nVotre requête a bien été reçue et sera examinée dans les plus brefs délais\nVeuillez trouvez ci dessous un résumé des informations renseignées:\n\n{}".format(
                name, message)

            send_mail(conf_subject, conf_message, 'testsovis@gmail.com', usermail, fail_silently=False)
            # /

            messages.add_message(request, messages.INFO, 'Votre message a bien été envoyé.')
            f = ContactForm()

            return render(request, 'contact.html', {'form': f})

    else:
        f = ContactForm()

    return render(request, 'contact.html', {'form': f})