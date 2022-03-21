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


# Pages
def unknown(request):
    return render(request, '404.html')


def create(request):
    ldapid = request.GET['ldapid']  # ldapid
    id_halerror = False
    if 'iDhalerror' in request.GET:
        id_halerror = request.GET['iDhalerror']

    return render(request, 'create.html', {'data': "create",  # 'type': i_type,
                                           'ldapid': ldapid,  # 'from': datefrom, 'to': dateto,
                                           # 'entity': entity, #'extIds': ['a', 'b', 'c'],
                                           'halId_s': 'nullNone',
                                           'idRef': 'nullNone',
                                           'orcId': 'nullNone',
                                           'autres': 'nullNone',
                                           'form': forms.CreateCredentials(),
                                           'iDhalerror': id_halerror,
                                           }
                  # "'startDate': start_date,
                  # 'timeRange': "from:'" + datefrom + "',to:'" + dateto + "'"}
                  )


def check(request):
    # Connect to DB

    if request.user.is_authenticated and request.user.get_username() == 'visiteur':
        return redirect('unknown')

    es = esActions.es_connector()

    if 'struct' in request.GET:
        struct = request.GET['struct']
    else:
        struct = -1

    if 'type' in request.GET and 'id' in request.GET:
        i_type = request.GET['type']
        p_id = request.GET['id']

    elif request.user.is_authenticated:
        basereverse = 'check'
        default_data = "credentials"
        return default_checker(request, basereverse, default_data)

    else:  # retour à l'ancien système et redirect unknown s'il n'est pas identifié et les i_type et p_id ne sont pas connu
        return redirect('unknown')

    if 'data' in request.GET:
        data = request.GET['data']
    else:
        data = -1
    # /

    if data == -1:
        return render(request, 'create.html', {'data': viewsActions.create,
                                               # 'type': i_type, 'id': p_id, 'from': datefrom, 'to': dateto,
                                               'form': forms.CreateCredentials(),

                                               }
                      )

    # Get scope data
    if i_type == "rsr":
        field = "_id"
        key = 'halId_s'
        search_id = "*"
        index_pattern = "-researchers"

    elif i_type == "lab":
        field = "halStructId"
        key = "halStructId"
        search_id = p_id
        index_pattern = "-laboratories"

    ext_key = "harvested_from_ids"

    scope_param = esActions.scope_p(field, p_id)

    res = es.search(index=struct + "-" + search_id + index_pattern, body=scope_param)
    # on pointe sur index générique, car pas de LabHalId ?

    try:
        entity = res['hits']['hits'][0]['_source']
    except FileNotFoundError:
        return redirect('unknown')
    # /

    # Get first submittedDate_tdate date
    field = "harvested_from_ids"
    if i_type == "rsr":
        start_date_param = esActions.date_p(field, entity['halId_s'])

        try:

            res = es.search(index=struct + "-" + entity['labHalId'] + "-researchers-" + p_id + "-documents",
                            body=start_date_param)
            start_date = res['hits']['hits'][0]['_source']['submittedDate_tdate']
        except FileNotFoundError:
            start_date_param.pop("sort")
            res = es.search(index=struct + "-" + entity['labHalId'] + "-researchers-" + p_id + "-documents",
                            body=start_date_param)
            start_date = "2000"
    elif i_type == "lab":
        start_date_param = esActions.date_p(field, entity['halStructId'])

        try:

            res = es.search(index=struct + "-" + entity['halStructId'] + "-laboratories-documents",
                            body=start_date_param)
            start_date = res['hits']['hits'][0]['_source']['submittedDate_tdate']
        except FileNotFoundError:
            start_date_param.pop("sort")
            res = es.search(index=struct + "-" + entity['halStructId'] + "-laboratories-documents",
                            body=start_date_param)
            start_date = "2000"

    # /

    # Get parameters
    if 'from' in request.GET:
        datefrom = request.GET['from']
    else:
        datefrom = start_date[0:4] + '-01-01'

    if 'to' in request.GET:
        dateto = request.GET['to']
    else:
        dateto = datetime.today().strftime('%Y-%m-%d')
    # /

    hastoconfirm = False
    validate = False
    if i_type == "rsr":
        field = "authIdHal_s"
        hastoconfirm_param = esActions.confirm_p(field, entity['halId_s'], validate)

        # devrait être scindé en deux ex.count qui diffèrent selon lab ou rsr dans les if précédent
        #  par ex pour == if i_type == "rsr": : es.count(index=struct  + "-" + entity['halStructId']+"-"researchers-" + entity["ldapId"] +"-documents", body=hastoconfirm_param)['count'] > 0:

    if i_type == "lab":
        field = "labStructId_i"
        hastoconfirm_param = esActions.confirm_p(field, entity['halStructId'], validate)

    if es.count(index=struct + "*-documents", body=hastoconfirm_param)['count'] > 0:
        # devrait être scindé en deux ex.count qui diffèrent selon lab ou rsr dans les if précédent
        #  par ex pour == if i_type == "lab": : es.count(index=struct  + "-" + entity['halStructId']+"-documents", body=hastoconfirm_param)['count'] > 0:
        hastoconfirm = True

    print(hastoconfirm)

    if data == "state":
        field = "labHalId"
        rsr_param = esActions.scope_p(field, p_id)

        count = es.count(index="*-researchers", body=rsr_param)['count']

        rsrs = es.search(index="*-researchers", body=rsr_param, size=count)

        rsrs_cleaned = []

        for result in rsrs['hits']['hits']:
            rsrs_cleaned.append(result['_source'])
        print(rsrs_cleaned)
        return render(request, 'check.html',
                      {'struct': struct, 'data': data, 'type': i_type, 'id': p_id, 'from': datefrom, 'to': dateto,
                       'entity': entity,
                       'researchers': rsrs_cleaned,
                       'startDate': start_date,
                       'hasToConfirm': hastoconfirm,
                       'timeRange': "from:'" + datefrom + "',to:'" + dateto + "'"})

    if data == "-1" or data == "credentials":

        if i_type == "rsr":
            orcid = ''
            if 'orcId' in entity:
                orcid = entity['orcId']
            if 'orcId' in request.GET:
                orcid = request.GET['orcId']
            function = 0
            if 'function' in entity:
                function = entity['function']

            return render(request, 'check.html',
                          {'struct': struct, 'data': data, 'type': i_type, 'id': p_id, 'from': datefrom, 'to': dateto,
                           'entity': entity, 'extIds': ['a', 'b', 'c'],
                           'form': forms.validCredentials(halId_s=entity['halId_s'],
                                                          idRef=entity['idRef'], orcId=orcid,
                                                          function=function),
                           'startDate': start_date,
                           'hasToConfirm': hastoconfirm,
                           'timeRange': "from:'" + datefrom + "',to:'" + dateto + "'"})

        if i_type == "lab":
            return render(request, 'check.html',
                          {'struct': struct, 'data': data, 'type': i_type, 'id': p_id, 'from': datefrom, 'to': dateto,
                           'entity': entity,
                           'form': forms.validLabCredentials(halStructId=entity['halStructId'],
                                                             rsnr=entity['rsnr'],
                                                             idRef=entity['idRef']),
                           'startDate': start_date,
                           'hasToConfirm': hastoconfirm,
                           'timeRange': "from:'" + datefrom + "',to:'" + dateto + "'"})

    elif data == "research-description":

        if 'research_summary' not in entity:
            research_summary = ''
        else:
            research_summary = entity['research_summary']

        if 'research_projectsAndFundings' not in entity:
            research_projects_and_fundings = ''
        else:
            research_projects_and_fundings = entity['research_projectsAndFundings']

        if 'research_projectsInProgress' not in entity:
            research_projects_in_progress = ''
        else:
            research_projects_in_progress = entity['research_projectsInProgress']

        return render(request, 'check.html',
                      {'struct': struct, 'data': data, 'type': i_type, 'id': p_id, 'from': datefrom, 'to': dateto,
                       'entity': entity, 'extIds': ['a', 'b', 'c'],
                       'form': forms.setResearchDescription(research_summary=research_summary,
                                                            research_projectsInProgress=research_projects_in_progress,
                                                            research_projectsAndFundings=research_projects_and_fundings),
                       'startDate': start_date,
                       'research_summary': research_summary,
                       'research_projectsInProgress': research_projects_in_progress,
                       'research_projectsAndFundings': research_projects_and_fundings,
                       'hasToConfirm': hastoconfirm,
                       'timeRange': "from:'" + datefrom + "',to:'" + dateto + "'"})

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

        return render(request, 'check.html',
                      {'struct': struct, 'data': data, 'type': i_type, 'id': p_id, 'from': datefrom, 'to': dateto,
                       'validation': validation,
                       'entity': entity,
                       'concepts': concepts,
                       'startDate': start_date,
                       'hasToConfirm': hastoconfirm,
                       'timeRange': "from:'" + datefrom + "',to:'" + dateto + "'"})

    elif data == "guiding-keywords":
        return render(request, 'check.html',
                      {'struct': struct, 'data': data, 'type': i_type, 'id': p_id, 'from': datefrom, 'to': dateto,
                       'entity': entity,
                       'form': forms.setGuidingKeywords(
                           guidingKeywords=entity['guidingKeywords']),
                       'startDate': start_date,
                       'hasToConfirm': hastoconfirm,
                       'timeRange': "from:'" + datefrom + "',to:'" + dateto + "'"})

    elif data == "guiding-domains":

        domains = halConcepts.concepts()

        guiding_domains = []

        if 'guidingDomains' in entity:
            guiding_domains = entity['guidingDomains']

        return render(request, 'check.html',
                      {'struct': struct, 'data': data, 'type': i_type, 'id': p_id, 'from': datefrom, 'to': dateto,
                       'entity': entity,
                       'domains': domains,
                       'guidingDomains': guiding_domains,
                       'startDate': start_date,
                       'hasToConfirm': hastoconfirm,
                       'timeRange': "from:'" + datefrom + "',to:'" + dateto + "'"})

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
        ref_param = esActions.ref_p(scope_bool_type, ext_key, entity[key], validate, date_range_type, datefrom, dateto)

        if i_type == "rsr":
            count = \
                es.count(index=struct + "-" + entity["labHalId"] + "-researchers-" + entity['ldapId'] + "-documents",
                         body=ref_param)['count']
            references = es.search(
                index=struct + "-" + entity["labHalId"] + "-researchers-" + entity['ldapId'] + "-documents",
                body=ref_param, size=count)

        if i_type == "lab":
            count = es.count(index=struct + "-" + entity["halStructId"] + "-laboratories-documents",
                             body=ref_param)['count']
            references = es.search(
                index=struct + "-" + entity["halStructId"] + "-laboratories-documents",
                body=ref_param, size=count)

        references_cleaned = []

        for ref in references['hits']['hits']:
            references_cleaned.append(ref['_source'])
        # /

        return render(request, 'check.html',
                      {'struct': struct, 'data': data, 'type': i_type, 'id': p_id, 'from': datefrom, 'to': dateto,
                       'validation': validation,
                       'entity': entity,
                       'hasToConfirm': hastoconfirm,
                       'references': references_cleaned, 'startDate': start_date,
                       'timeRange': "from:'" + datefrom + "',to:'" + dateto + "'"})

    else:
        return redirect('unknown')


def dashboard(request):
    # Get parameters
    if 'struct' in request.GET:
        struct = request.GET['struct']
    else:
        struct = -1

    if 'ldapid' in request.GET:
        ldapid = request.GET['ldapid']
    else:
        ldapid = None

    if 'type' in request.GET and 'id' in request.GET:  # réutilisation de l'ancien système
        i_type = request.GET['type']
        p_id = request.GET['id']

    elif request.user.is_authenticated:
        basereverse = 'dashboard'
        return default_checker(request, basereverse)

    else:  # retour à l'ancien système et redirect unknown s'il n'est pas identifié et les i_type et p_id ne sont pas connu
        return redirect('unknown')
    # /
    # Connect to DB
    es = esActions.es_connector()

    # Get scope data
    if i_type == "rsr":
        field = "_id"
        key = 'halId_s'
        search_id = "*"
        index_pattern = "-researchers"

    elif i_type == "lab":
        field = "halStructId"
        key = "halStructId"
        search_id = p_id
        index_pattern = "-laboratories"

    scope_param = esActions.scope_p(field, p_id)

    res = es.search(index=struct + "-" + search_id + index_pattern,
                    body=scope_param)  # on pointe sur index générique, car pas de LabHalId ?

    try:
        entity = res['hits']['hits'][0]['_source']
    except FileNotFoundError:
        return redirect('unknown')
    # /

    hastoconfirm = False

    validate = False
    if i_type == "rsr":
        field = "authIdHal_s"
        hastoconfirm_param = esActions.confirm_p(field, entity['halId_s'], validate)

        # devrait être scindé en deux ex.count qui diffèrent selon lab ou rsr dans les if précédent
        #  par ex pour == if i_type == "rsr": : es.count(index=struct  + "-" + entity['halStructId']+"-"researchers-" +
        #  entity["ldapId"] +"-documents", body=hastoconfirm_param)['count'] > 0:

    if i_type == "lab":
        field = "labStructId_i"
        hastoconfirm_param = esActions.confirm_p(field, entity['halStructId'], validate)

    if es.count(index=struct + "*-documents", body=hastoconfirm_param)[
        'count'] > 0:  # devrait être scindé en deux ex.count qui diffèrent selon lab ou rsr dans les if précédent
        #  par ex pour == if i_type == "lab": : es.count(index=struct  + "-" + entity['halStructId']+"-documents", body=hastoconfirm_param)['count'] > 0:
        hastoconfirm = True

    # Get first submittedDate_tdate date
    if i_type == "rsr":
        indexsearch = struct + '-' + entity['labHalId'] + "-researchers-" + entity['ldapId'] + "-documents"
        try:
            start_date_param = esActions.date_all()
            res = es.search(index=indexsearch, body=start_date_param)

        except FileNotFoundError:
            start_date_param.pop("sort")
            res = es.search(index=indexsearch, body=start_date_param)

        filtrechercheur = '_index: "' + indexsearch + '"'
        filtre_lab_a = ''
        filtre_lab_b = ''
    elif i_type == "lab":
        field = "harvested_from_ids"
        start_date_param = esActions.date_p(field, entity['halStructId'])

        res = es.search(index=struct + '-' + p_id + "-laboratories-documents", body=start_date_param)
        filtrechercheur = ''
        filtre_lab_a = 'harvested_from_ids: "' + p_id + '"'
        filtre_lab_b = 'labHalId.keyword: "' + p_id + '"'

    try:
        start_date = res['hits']['hits'][0]['_source']['submittedDate_tdate']
    except FileNotFoundError:
        start_date = "2000"
    # /

    # Get parameters
    if 'from' in request.GET:
        datefrom = request.GET['from']
    else:
        datefrom = start_date[0:4] + '-01-01'

    if 'to' in request.GET:
        dateto = request.GET['to']
    else:
        dateto = datetime.today().strftime('%Y-%m-%d')

    ext_key = "harvested_from_ids"
    # /

    return render(request, 'dashboard.html',
                  {'ldapid': ldapid, 'struct': struct, 'type': i_type, 'id': p_id, 'from': datefrom, 'to': dateto,
                   'entity': entity,
                   'hasToConfirm': hastoconfirm,
                   'ext_key': ext_key,
                   'key': entity[key],
                   'filterRsr': filtrechercheur,
                   'filterlabA': filtre_lab_a,
                   'filterlabB': filtre_lab_b,
                   'startDate': start_date,
                   'timeRange': "from:'" + datefrom + "',to:'" + dateto + "'"})


def references(request):
    # Get parameters
    if 'struct' in request.GET:
        struct = request.GET['struct']
    else:
        struct = -1

    if 'ldapid' in request.GET:
        ldapid = request.GET['ldapid']
    else:
        ldapid = None

    if 'type' in request.GET and 'id' in request.GET:  # réutilisation de l'ancien système
        i_type = request.GET['type']
        p_id = request.GET['id']

    elif request.user.is_authenticated:
        basereverse = 'references'
        return default_checker(request, basereverse)

    else:  # retour à l'ancien système et redirect unknown s'il n'est pas identifié et les i_type et p_id ne sont pas connu
        return redirect('unknown')

    if 'filter' in request.GET:
        filter = request.GET['filter']
    else:
        filter = -1

    # /
    # Connect to DB
    es = esActions.es_connector()

    # Get scope data
    if i_type == "rsr":
        field = "_id"
        key = 'halId_s'
        search_id = "*"
        index_pattern = "-researchers"

    elif i_type == "lab":
        field = "halStructId"
        key = "halStructId"
        search_id = p_id
        index_pattern = "-laboratories"

    ext_key = "harvested_from_ids"

    scope_param = esActions.scope_p(field, p_id)

    res = es.search(index=struct + "-" + search_id + index_pattern,
                    body=scope_param)  # on pointe sur index générique, car pas de LabHalId ?

    try:
        entity = res['hits']['hits'][0]['_source']
    except FileNotFoundError:
        return redirect('unknown')
    # /

    # Get first submittedDate_tdate date
    field = "harvested_from_ids"

    if i_type == "rsr":
        start_date_param = esActions.date_p(field, entity['halId_s'])

        res = es.search(index=struct + "-" + entity['labHalId'] + "-researchers-" + entity['ldapId'] + "-documents",
                        body=start_date_param)  # labHalId est-il là ?
    elif i_type == "lab":
        start_date_param = esActions.date_p(field, entity['halStructId'])

        res = es.search(index=struct + "-" + p_id + "-laboratories-documents", body=start_date_param)

    start_date = res['hits']['hits'][0]['_source']['submittedDate_tdate']
    # /

    # Get parameters
    if 'from' in request.GET:
        datefrom = request.GET['from']
    else:
        datefrom = start_date[0:4] + '-01-01'

    if 'to' in request.GET:
        dateto = request.GET['to']
    else:
        dateto = datetime.today().strftime('%Y-%m-%d')
    # /

    hastoconfirm = False
    field = "harvested_from_ids"
    validate = False
    if i_type == "rsr":

        hastoconfirm_param = esActions.confirm_p(field, entity['halId_s'], validate)

        if es.count(index=struct + "-" + entity['labHalId'] + "-researchers-" + entity['ldapId'] + "-documents",
                    body=hastoconfirm_param)['count'] > 0:
            hastoconfirm = True
    if i_type == "lab":

        hastoconfirm_param = esActions.confirm_p(field, entity['halStructId'], validate)

        if es.count(index=struct + "-" + entity['halStructId'] + "-laboratories-documents", body=hastoconfirm_param)[
            'count'] > 0:
            hastoconfirm = True

    # Get references
    scope_bool_type = "filter"
    validate = True
    date_range_type = "submittedDate_tdate"
    ref_param = esActions.ref_p_filter(filter, scope_bool_type, ext_key, entity[key], validate, date_range_type,
                                       datefrom,
                                       dateto)

    if i_type == "rsr":
        count = es.count(index=struct + "-" + entity["labHalId"] + "-researchers-" + entity['ldapId'] + "-documents",
                         body=ref_param)['count']
        references = es.search(
            index=struct + "-" + entity["labHalId"] + "-researchers-" + entity['ldapId'] + "-documents",
            body=ref_param, size=count)

    if i_type == "lab":
        count = es.count(index=struct + "-" + entity["halStructId"] + "-laboratories-documents", body=ref_param)[
            'count']
        references = es.search(index=struct + "-" + entity["halStructId"] + "-laboratories-documents", body=ref_param,
                               size=count)

    references_cleaned = []

    for ref in references['hits']['hits']:
        references_cleaned.append(ref['_source'])
    # /
    return render(request, 'references.html',
                  {'ldapid': ldapid, 'struct': struct, 'filter': filter, 'type': i_type, 'id': p_id, 'from': datefrom,
                   'to': dateto,
                   'entity': entity,
                   'hasToConfirm': hastoconfirm,
                   'references': references_cleaned, 'startDate': start_date,
                   'timeRange': "from:'" + datefrom + "',to:'" + dateto + "'"})


@xframe_options_exempt
def terminology(request):
    # Get parameters
    if 'struct' in request.GET:
        struct = request.GET['struct']
    else:
        struct = -1

    if 'ldapid' in request.GET:
        ldapid = request.GET['ldapid']
    else:
        ldapid = None

    if 'type' in request.GET and 'id' in request.GET:  # réutilisation de l'ancien système
        i_type = request.GET['type']
        p_id = request.GET['id']

    elif request.user.is_authenticated:
        basereverse = 'terminology'
        return default_checker(request, basereverse)

    else:  # retour à l'ancien système et redirect unknown s'il n'est pas identifié et les i_type et p_id ne sont pas connu
        return redirect('unknown')

    if 'export' in request.GET:
        export = request.GET['export']
    else:
        export = False
    # /
    # Connect to DB
    es = esActions.es_connector()

    # Get scope data
    if i_type == "rsr":
        field = "_id"
        search_id = "*"
        index_pattern = "-researchers"

    elif i_type == "lab":
        field = "halStructId"
        search_id = p_id
        index_pattern = "-laboratories"

    scope_param = esActions.scope_p(field, p_id)

    res = es.search(index=struct + "-" + search_id + index_pattern,
                    body=scope_param)  # on pointe sur index générique, car pas de LabHalId ?

    try:
        entity = res['hits']['hits'][0]['_source']
    except FileNotFoundError:
        return redirect('unknown')
    # /

    hastoconfirm = False

    validate = False
    field = "harvested_from_ids"

    if i_type == "rsr":
        hastoconfirm_param = esActions.confirm_p(field, entity['halId_s'], validate)

    if i_type == "lab":
        hastoconfirm_param = esActions.confirm_p(field, entity['halStructId'], validate)

    if es.count(index="*-documents", body=hastoconfirm_param)['count'] > 0:
        hastoconfirm = True

    # Get first submittedDate_tdate date
    field = "harvested_from_ids"

    if i_type == "rsr":
        start_date_param = esActions.date_p(field, entity['halId_s'])

    elif i_type == "lab":
        start_date_param = esActions.date_p(field, entity['halStructId'])

    res = es.search(index=struct + "-*-documents", body=start_date_param)
    start_date = res['hits']['hits'][0]['_source']['submittedDate_tdate']
    # /

    # Get parameters
    if 'from' in request.GET:
        datefrom = request.GET['from']
    else:
        datefrom = start_date[0:4] + '-01-01'

    if 'to' in request.GET:
        dateto = request.GET['to']
    else:
        dateto = datetime.today().strftime('%Y-%m-%d')
    # /

    if i_type == "lab":
        entity['concepts'] = json.dumps(entity['concepts'])

    if i_type == "rsr":
        entity['concepts'] = json.dumps(entity['concepts'])

    entity['concepts'] = json.loads(entity['concepts'])

    if i_type == "rsr":

        from pprint import pprint

        pprint(entity['concepts'])

        if 'children' in entity['concepts']:
            for children in list(entity['concepts']['children']):
                if children['state'] == 'invalidated':
                    entity['concepts']['children'].remove(children)

                if 'children' in children:
                    for children1 in list(children['children']):
                        if children1['state'] == 'invalidated':
                            children['children'].remove(children1)

                        if 'children' in children1:
                            for children2 in list(children1['children']):
                                if children2['state'] == 'invalidated':
                                    children1['children'].remove(children2)

    if i_type == "lab":

        if 'children' in entity['concepts']:
            for children in list(entity['concepts']['children']):
                print(children['id'])
                state = 'invalidated'
                if 'researchers' in children:
                    for rsr in children['researchers']:
                        print(rsr)
                        if rsr['state'] == 'validated':
                            state = 'validated'
                    if state == "invalidated":
                        entity['concepts']['children'].remove(children)

                if 'children' in children:
                    for children1 in list(children['children']):
                        state = 'invalidated'
                        if 'researchers' in children1:
                            for rsr in children1['researchers']:
                                if rsr['state'] == 'validated':
                                    state = 'validated'
                            if state == "invalidated":
                                children['children'].remove(children1)

                        if 'children' in children1:
                            for children2 in list(children1['children']):
                                state = 'invalidated'
                                if 'researchers' in children2:
                                    for rsr in children2['researchers']:
                                        if rsr['state'] == 'validated':
                                            state = 'validated'
                                    if state == "invalidated":
                                        children1['children'].remove(children2)

    if export:
        return render(request, 'terminology_ext.html',
                      {'ldapid': ldapid, 'struct': struct, 'type': i_type, 'id': p_id, 'from': datefrom, 'to': dateto,
                       'entity': entity,
                       'hasToConfirm': hastoconfirm,
                       'startDate': start_date,
                       'timeRange': "from:'" + datefrom + "',to:'" + dateto + "'"})
    else:
        return render(request, 'terminology.html',
                      {'ldapid': ldapid, 'struct': struct, 'type': i_type, 'id': p_id, 'from': datefrom, 'to': dateto,
                       'entity': entity,
                       'hasToConfirm': hastoconfirm,
                       'startDate': start_date,
                       'timeRange': "from:'" + datefrom + "',to:'" + dateto + "'"})


def wordcloud(request):
    # Get parameters
    if 'struct' in request.GET:
        struct = request.GET['struct']
    else:
        struct = -1

    if 'ldapid' in request.GET:
        ldapid = request.GET['ldapid']
    else:
        ldapid = None

    if 'type' in request.GET and 'id' in request.GET:  # réutilisation de l'ancien système
        i_type = request.GET['type']
        p_id = request.GET['id']

    elif request.user.is_authenticated:
        basereverse = 'wordcloud'
        return default_checker(request, basereverse)

    else:  # retour à l'ancien système et redirect unknown s'il n'est pas identifié et les i_type et p_id ne sont pas connu
        return redirect('unknown')
    # /
    # Connect to DB
    es = esActions.es_connector()

    # Get scope data
    if i_type == "rsr":
        field = "_id"
        key = 'halId_s'
        search_id = "*"
        index_pattern = "-researchers"

    elif i_type == "lab":
        field = "halStructId"
        key = "halStructId"
        search_id = p_id
        index_pattern = "-laboratories"

    ext_key = "harvested_from_ids"

    scope_param = esActions.scope_p(field, p_id)

    res = es.search(index=struct + "-" + search_id + index_pattern,
                    body=scope_param)  # on pointe sur index générique, car pas de LabHalId ?

    try:
        entity = res['hits']['hits'][0]['_source']
    except FileNotFoundError:
        return redirect('unknown')
    # /

    hastoconfirm = False

    field = "harvested_from_ids"
    validate = False
    if i_type == "rsr":
        hastoconfirm_param = esActions.confirm_p(field, entity['halId_s'], validate)

    if i_type == "lab":
        hastoconfirm_param = esActions.confirm_p(field, entity['halStructId'], validate)

    if es.count(index=struct + "*-documents", body=hastoconfirm_param)['count'] > 0:
        hastoconfirm = True

    # Get first submittedDate_tdate date
    field = "harvested_from_ids"

    if i_type == "rsr":
        start_date_param = esActions.date_p(field, entity['halId_s'])
        indexsearch = struct + '-' + entity['labHalId'] + "-researchers-" + entity['ldapId'] + "-documents"
        filtrechercheur = '_index: "' + indexsearch + '"'

    elif i_type == "lab":

        start_date_param = esActions.date_p(field, entity['halStructId'])
        filtrechercheur = ''

    res = es.search(index=struct + "*-documents", body=start_date_param)
    start_date = res['hits']['hits'][0]['_source']['submittedDate_tdate']
    # /

    # Get parameters
    if 'from' in request.GET:
        datefrom = request.GET['from']
    else:
        datefrom = start_date[0:4] + '-01-01'

    if 'to' in request.GET:
        dateto = request.GET['to']
    else:
        dateto = datetime.today().strftime('%Y-%m-%d')
    # /

    return render(request, 'wordcloud.html',
                  {'ldapid': ldapid, 'struct': struct, 'type': i_type, 'id': p_id, 'from': datefrom, 'to': dateto,
                   'entity': entity,
                   'hasToConfirm': hastoconfirm,
                   'filterRsr': filtrechercheur,
                   'startDate': start_date,
                   'timeRange': "from:'" + datefrom + "',to:'" + dateto + "'"})


def tools(request):
    # Get parameters
    if 'struct' in request.GET:
        struct = request.GET['struct']
    else:
        struct = -1

    if 'ldapid' in request.GET:
        ldapid = request.GET['ldapid']
    else:
        ldapid = None

    if 'type' in request.GET and 'id' in request.GET:  # réutilisation de l'ancien système
        i_type = request.GET['type']
        p_id = request.GET['id']

    elif request.user.is_authenticated:
        basereverse = 'dashboard'
        return default_checker(request, basereverse)

    else:  # retour à l'ancien système et redirect unknown s'il n'est pas identifié et les i_type et p_id ne sont pas connu
        return redirect('unknown')
    # /
    # Connect to DB
    es = esActions.es_connector()

    # Get scope data
    if i_type == "lab":
        field = "halStructId"
        key = "halStructId"
        search_id = p_id
        index_pattern = "-laboratories"

    ext_key = "harvested_from_ids"

    scope_param = esActions.scope_p(field, p_id)

    res = es.search(index=struct + "-" + search_id + index_pattern,
                    body=scope_param)  # on pointe sur index générique, car pas de LabHalId ?

    try:
        entity = res['hits']['hits'][0]['_source']
    except FileNotFoundError:
        return redirect('unknown')
    # /

    hastoconfirm = False

    validate = False
    if i_type == "lab":
        field = "labStructId_i"
        hastoconfirm_param = esActions.confirm_p(field, entity['halStructId'], validate)

    if es.count(index="*-documents", body=hastoconfirm_param)[
        'count'] > 0:  # devrait être scindé en deux ex.count qui diffèrent selon "lab" ou rsr dans les if précédent
        #  par ex pour == if i_type == "lab": : es.count(index=struct  + "-" + entity['halStructId']+"-documents", body=hastoconfirm_param)['count'] > 0:
        hastoconfirm = True

    # Get first submittedDate_tdate date
    if i_type == "lab":
        field = "harvested_from_ids"
        start_date_param = esActions.date_p(field, entity['halStructId'])

        res = es.search(index=struct + '-' + p_id + "-laboratories-documents", body=start_date_param)

    try:
        start_date = res['hits']['hits'][0]['_source']['submittedDate_tdate']
    except FileNotFoundError:
        start_date = "2000"
    # /

    # Get parameters
    if 'from' in request.GET:
        datefrom = request.GET['from']
    else:
        datefrom = start_date[0:4] + '-01-01'

    if 'to' in request.GET:
        dateto = request.GET['to']
    else:
        dateto = datetime.today().strftime('%Y-%m-%d')
    # /

    if 'data' in request.GET:
        data = request.GET['data']
    else:
        data = "hceres"

    if data == "hceres" or data == -1:
        return render(request, 'tools.html',
                      {'ldapid': ldapid, 'struct': struct, 'data': data, 'type': i_type, 'id': p_id, 'from': datefrom,
                       'to': dateto,
                       'entity': entity,
                       'hasToConfirm': hastoconfirm,
                       'ext_key': ext_key,
                       'key': entity[key],
                       'startDate': start_date,
                       'timeRange': "from:'" + datefrom + "',to:'" + dateto + "'"})
    elif data == "consistency":

        consistencyvalues = viewsActions.cohesion(struct, p_id, datefrom, dateto)

        return render(request, 'tools.html',
                      {'ldapid': ldapid, 'struct': struct, 'data': data, 'type': i_type, 'id': p_id, 'from': datefrom,
                       'to': dateto,
                       'entity': entity,
                       'consistency': consistencyvalues,
                       'startDate': start_date,
                       'hasToConfirm': hastoconfirm,
                       'timeRange': "from:'" + datefrom + "',to:'" + dateto + "'"})


def index(request):
    # Get parameters
    indexcat = request.GET['indexcat']
    indexstruct = request.GET['indexstruct']

    if 'struct' in request.GET:
        struct = request.GET['struct']
    else:
        struct = -1

    if 'type' in request.GET:
        i_type = request.GET['type']
    else:
        i_type = -1

    if 'id' in request.GET:
        p_id = request.GET['id']
    else:
        p_id = -1

    if 'ldapid' in request.GET:
        ldapid = request.GET['ldapid']
    else:
        ldapid = None
    # /

    # Connect to DB
    es = esActions.es_connector()

    indextype = ""
    if indexcat == "lab":
        indextype = "*-laboratories"

    elif indexcat == "rsr":
        indextype = "*-researchers"

    scope_param = esActions.scope_all()
    count = es.count(index=indexstruct + indextype, body=scope_param)['count']
    res = es.search(index=indexstruct + indextype, body=scope_param, size=count)
    entities = res['hits']['hits']
    cleaned_entities = []

    for entity in entities:
        cleaned_entities.append(entity['_source'])

    if indexcat == "lab":
        cleaned_entities = sorted(cleaned_entities, key=lambda k: k['acronym'])
    elif indexcat == "rsr":
        cleaned_entities = sorted(cleaned_entities, key=lambda k: k['lastName'])
    # /
    if i_type == -1 and p_id == -1:  # Si l'i_type et l'id ne sont pas renseignés, ceux ci ne sont pas renvoyés
        # → évite des erreurs lors des vérifications pour les autres pages dans le cas d'un -1
        return render(request, 'index.html',
                      {'entities': cleaned_entities, 'indexcat': indexcat, 'indexstruct': indexstruct,
                       'ldapid': ldapid})
    else:  # L'i_type et l'id sont renvoyés dans la requète : persistence du profil choisi/connecté en amont.
        return render(request, 'index.html',
                      {'entities': cleaned_entities, 'type': i_type, 'indexcat': indexcat, 'indexstruct': indexstruct,
                       'id': p_id, 'struct': struct, 'ldapid': ldapid})


def search(request):  # Revoir la fonction
    # Connect to DB
    es = esActions.es_connector()

    date_param = {
        "aggs": {
            "min_date": {"min": {"field": "submittedDate_tdate"}},
        }
    }

    min_date = es.search(index="*-documents", body=date_param, size=0)['aggregations']['min_date']['value_as_string']

    # Get parameters
    if 'struct' in request.GET:
        struct = request.GET['struct']
    else:
        struct = -1

    if 'type' in request.GET:
        i_type = request.GET['type']
    else:
        i_type = -1

    if 'id' in request.GET:
        p_id = request.GET['id']
    else:
        p_id = -1
    if 'from' in request.GET:
        datefrom = request.GET['from']
    else:
        datefrom = min_date[0:4] + '-01-01'

    if 'to' in request.GET:
        dateto = request.GET['to']
    else:
        dateto = datetime.today().strftime('%Y-%m-%d')

    if 'ldapid' in request.GET:
        ldapid = request.GET['ldapid']
    else:
        ldapid = None

    if request.method == 'POST':

        # Connect to DB
        es = esActions.es_connector()

        index = request.POST.get("f_index")
        search = request.POST.get("f_search")

        if "*-researchers-*-doc*" in index:  # == 'documents':
            search_param = {
                "query": {"bool": {"must": [{"query_string": {"query": search}}],
                                   "filter": [{"match": {"validated": "true"}}]}}
            }
        elif "*-researchers" in index:  # =='researchers':
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
        return render(request, 'search.html',
                      {'struct': struct, 'type': i_type, 'id': p_id, 'form': forms.search(val=search),
                       'count': p_res['count'],
                       'timeRange': "from:'" + datefrom + "',to:'" + dateto + "'",
                       'filter': search, 'index': index, 'search': search,
                       'results': res_cleaned, 'from': datefrom, 'to': dateto,
                       'startDate': min_date, 'ldapid': ldapid})

    return render(request, 'search.html',
                  {'struct': struct, 'type': i_type, 'id': p_id, 'form': forms.search(), 'from': datefrom, 'to': dateto,
                   'startDate': min_date, 'filter': '', 'ldapid': ldapid})


def presentation(request):
    # Get parameters
    if 'struct' in request.GET:
        struct = request.GET['struct']
    else:
        struct = -1

    if 'type' in request.GET:
        i_type = request.GET['type']
    else:
        i_type = -1

    if 'id' in request.GET:
        p_id = request.GET['id']
    else:
        p_id = -1

    if 'ldapid' in request.GET:
        ldapid = request.GET['ldapid']
    else:
        ldapid = None
    # /
    return render(request, 'presentation.html', {'struct': struct, 'type': i_type, 'id': p_id, 'ldapid': ldapid})


def ressources(request):
    # Get parameters
    if 'struct' in request.GET:
        struct = request.GET['struct']
    else:
        struct = -1

    if 'type' in request.GET:
        i_type = request.GET['type']
    else:
        i_type = -1

    if 'id' in request.GET:
        p_id = request.GET['id']
    else:
        p_id = -1

    if 'ldapid' in request.GET:
        ldapid = request.GET['ldapid']
    else:
        ldapid = None
    # /
    return render(request, 'ressources.html', {'struct': struct, 'type': i_type, 'id': p_id, 'ldapid': ldapid})


def faq(request):
    # Get parameters
    if 'struct' in request.GET:
        struct = request.GET['struct']
    else:
        struct = -1

    if 'type' in request.GET:
        i_type = request.GET['type']
    else:
        i_type = -1

    if 'id' in request.GET:
        p_id = request.GET['id']
    else:
        p_id = -1

    if 'ldapid' in request.GET:
        ldapid = request.GET['ldapid']
    else:
        ldapid = None
    # /
    return render(request, 'faq.html', {'struct': struct, 'type': i_type, 'id': p_id, 'ldapid': ldapid})


def contact(request):
    # Get parameters
    if 'struct' in request.GET:
        struct = request.GET['struct']
    else:
        struct = -1

    if 'type' in request.GET:
        i_type = request.GET['type']
    else:
        i_type = -1

    if 'id' in request.GET:
        p_id = request.GET['id']
    else:
        p_id = -1

    if 'ldapid' in request.GET:
        ldapid = request.GET['ldapid']
    else:
        ldapid = None
    # /
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

            return render(request, 'contact.html',
                          {'struct': struct, 'type': i_type, 'id': p_id, 'form': f, 'ldapid': ldapid})

    else:
        f = ContactForm()

    return render(request, 'contact.html', {'struct': struct, 'type': i_type, 'id': p_id, 'form': f, 'ldapid': ldapid})


def useful_links(request):
    # Get parameters
    if 'struct' in request.GET:
        struct = request.GET['struct']
    else:
        struct = -1

    if 'type' in request.GET:
        i_type = request.GET['type']
    else:
        i_type = -1

    if 'id' in request.GET:
        p_id = request.GET['id']
    else:
        p_id = -1

    if 'ldapid' in request.GET:
        ldapid = request.GET['ldapid']
    else:
        ldapid = None
    # /
    return render(request, 'useful_links.html', {'struct': struct, 'type': i_type, 'id': p_id, 'ldapid': ldapid})


# utiliser cette fonction pour call log_checker
"""
    default_data ='' #use only if needed that parameter
    basereverse = ''
    i_type, p_id = log_checker(request, basereverse,default_data)
    print(type)
    print(id)
"""


def default_checker(request, basereverse, default_data=None):
    p_id = request.user.get_username()  # check si l'utilisateur est log
    print(p_id)
    p_id = p_id.replace(viewsActions.patternCas, '').lower()

    if p_id == 'adminlab':  # si p_id adminlab on considère que son i_type par défaut est lab
        print("1st option")
        indexcat = "lab"
        base_url = reverse('index')
        query_string = urlencode({'indexcat': indexcat, 'indexstruct': '198307662'})
        url = '{}?{}'.format(base_url, query_string)
        print(url)
        return redirect(url)
        print("error")

    if p_id == "invitamu":
        print("2nd option")
        indexcat = "rsr"
        base_url = reverse('index')
        query_string = urlencode({'indexcat': indexcat, 'indexstruct': '130015332'})
        url = '{}?{}'.format(base_url, query_string)
        return redirect(url)

    elif not p_id == 'adminlab' and not p_id == 'visiteur' and not p_id == 'invitamu' and not p_id == -1:
        # si ce n'est pas adminlab ni un visiteur → c'est un chercheur
        print("3rd option")
        i_type = "rsr"
        base_url = reverse(basereverse)  # élément à changer en fonction de la fonction effectuant le call
        if default_data is not None:
            default_data = "credentials"
            query_string = urlencode({'type': i_type, 'id': p_id, 'data': default_data})
        else:
            query_string = urlencode({'type': i_type, 'id': p_id})
        print(query_string)
        url = '{}?{}'.format(base_url, query_string)
        return redirect(url)

    else:  # sinon il est inconnu et doit aller dans l'index pour faire ses choix, car on ne peut pas le suivre
        return redirect('unknown')
