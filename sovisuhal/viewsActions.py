import json
from bs4 import BeautifulSoup
from datetime import datetime

from urllib.request import urlopen

from django.http import HttpResponse
from django.shortcuts import render, redirect

from sovisuhal.libs.elasticHal import indexe_chercheur, collecte_docs
from . import forms, settings
from .libs import utils, libsElastichal, esActions

from sovisuhal.libs.archivesOuvertes import getConceptsAndKeywords

import pandas as pd
from io import BytesIO as IO

try:
    from decouple import config
    from ldap3 import Server, Connection, ALL
    from uniauth.decorators import login_required

    mode = config("mode")  # Prod --> mode = 'Prod' en env Var
    patternCas = 'cas-utln-'  # motif à enlever aux identifiants CAS
except:
    from django.contrib.auth.decorators import login_required

    mode = "Dev"
    patternCas = ''  # motif à enlever aux identifiants CAS


@login_required
def admin_access_login(request):
    if not request.user.is_authenticated:
        return redirect('%s?next=%s' % (settings.LOGIN_URL, '/'))
    else:
        auth_user = request.user.get_username().lower()

        if auth_user == 'admin':
            return redirect('/admin/')
        elif auth_user == 'adminlab':
            return redirect("/index/?indexcat=lab&indexstruct=198307662")
        elif auth_user == 'invitamu':
            return redirect("/index/?indexcat=rsr&indexstruct=130015332")
        elif auth_user == 'visiteur':
            return redirect("/index/?indexcat=rsr&indexstruct=198307662")
        else:
            # auth_user = request.user.get_username()
            auth_user = auth_user.replace(patternCas, '').lower()
            # check présence auth_user
            es = esActions.es_connector()

            field = "_id"
            scope_param = esActions.scope_p(field, auth_user)
            count = es.count(index="*-researchers", body=scope_param)['count']
            if count > 0:
                res = es.search(index="*-researchers", body=scope_param, size=count)
                entity = res['hits']['hits'][0]['_source']
                struct = entity['structSirene']
                return redirect('check/?struct=' + struct + '&type=rsr&id=' + auth_user + '&from=1990-01-01&to=now&data=credentials')
            else:
                return redirect('create/?ldapid=' + auth_user + '&halId_s=nullNone&orcId=nullNone&idRef=nullNone')

    print("cas raté")
    return render(request, '404.html')




def create_credentials(request):
    ldapId = request.GET['ldapid']
    idRef = request.POST.get('f_IdRef')
    idhal = request.POST.get('f_halId_s')
    orcId = request.POST.get('f_orcId')
    # structId = request.POST.get ('structId')
    tempoLab = request.POST.get('f_labo')  # chaine de caractère
    tempoLab = tempoLab.replace("'", "")
    tempoLab = tempoLab.replace('(', '')
    tempoLab = tempoLab.replace(')', '')
    tempoLab = tempoLab.split(',')
    labo = tempoLab[0].strip()  # halid
    accroLab = tempoLab[1].strip()
    # resultat
    Chercheur = indexe_chercheur(ldapId, accroLab, labo, idhal, idRef, orcId)

    idhal_test = idhal_checkout(idhal)

    if idhal_test == 0:
        auth_user = request.user.get_username().lower()
        print("idhal not found")
        return redirect('/create/?ldapid=' + ldapId + '&halId_s=nullNone&orcId=nullNone&idRef=nullNone&iDhalerror=True')

    else:

        print("idhal found")
        collecte_docs(Chercheur)

        # récupération du struct du nouveau profil pour la redirection
        es = esActions.es_connector()
        field = "halId_s"
        scope_param = esActions.scope_p(field, idhal)
        count = es.count(index="*-researchers", body=scope_param)['count']
        res = es.search(index="*-researchers", body=scope_param, size=count)
        entity = res['hits']['hits'][0]['_source']
        struct = entity['structSirene']
        # /
        # name,type,function,mail,lab,supannAffectation,supannEntiteAffectationPrincipale,halId_s,labHalId,idRef,structDomain,firstName,lastName,aurehalId

        return redirect(
            '/check/?struct=' + struct +'&type=rsr&id=' + ldapId + '&orcId=' + orcId + '&from=1990-01-01&to=now&data=credentials')


# Redirects

def validate_references(request):
    # Get parameters
    if 'struct' in request.GET:
        struct = request.GET['struct']
    else:
        return redirect('unknown')

    if 'type' in request.GET:
        type = request.GET['type']
    else:
        return redirect('unknown')
    if 'id' in request.GET and 'validation' in request.GET:
        id = request.GET['id']
        validation = request.GET['validation']
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

    if int(validation) == 0:
        validate = True
    elif int(validation) == 1:
        validate = False

    # Connect to DB
    es = esActions.es_connector()

    # Get scope informations
    if type == "rsr":
        scope_param = esActions.scope_p("_id", id)

        res = es.search(index=struct + "-*-researchers", body=scope_param)
        try:
            entity = res['hits']['hits'][0]['_source']
        except:
            return redirect('unknown')

        if request.method == 'POST':

            toValidate = request.POST.get("toValidate", "").split(",")
            for docid in toValidate:
                es.update(index=struct + '-' + entity['labHalId'] + "-researchers-" + entity['ldapId'] + "-documents",
                          refresh='wait_for', id=docid,
                          body={"doc": {"validated": validate}})
                try:
                    es.update(index=struct + '-' + entity["labHalId"] + "-laboratories-documents", refresh='wait_for',
                              id=docid,
                              body={"doc": {"validated": validate}})
                except:
                    pass  # doc du chercheur pas dans le labo

    if type == "lab":
        scope_param = esActions.scope_p("_id", id)

        res = es.search(index=struct + "-*-laboratories", body=scope_param)
        try:
            entity = res['hits']['hits'][0]['_source']
        except:
            return redirect('unknown')

        if request.method == 'POST':
            toValidate = request.POST.get("toValidate", "").split(",")
            for docid in toValidate:
                es.update(index=struct + '-' + entity["halStructId"] + "-laboratories-documents", refresh='wait_for',
                          id=docid,
                          body={"doc": {"validated": validate}})

    return redirect(
        '/check/?struct=' + struct + '&type=' + type + '&id=' + id + '&from=' + dateFrom + '&to=' + dateTo + '&data=' + data + '&validation=' + validation)


def validate_guiding_domains(request):
    # Get parameters
    if 'struct' in request.GET:
        struct = request.GET['struct']
    else:
        return redirect('unknown')

    if 'type' in request.GET and 'id' in request.GET:
        type = request.GET['type']
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
    es = esActions.es_connector()

    if request.method == 'POST':

        toValidate = request.POST.get("toValidate", "").split(',')

        if type == "rsr":
            scope_param = esActions.scope_p("_id", id)

            res = es.search(index=struct + "-*-researchers", body=scope_param)
            try:
                entity = res['hits']['hits'][0]['_source']
            except:
                return redirect('unknown')

            es.update(index=struct + "-" + entity['labHalId'] + "-researchers", refresh='wait_for', id=id,
                      body={"doc": {"guidingDomains": toValidate}})

        if type == "lab":
            es.update(index=struct + "-" + id + "-laboratories", refresh='wait_for', id=id,
                      body={"doc": {"guidingDomains": toValidate}})

    return redirect('/check/?struct=' + struct + '&type=' + type + '&id=' + id + '&from=' + dateFrom + '&to=' + dateTo + '&data=' + data)


def validate_expertise(request):
    # Get parameters
    if 'struct' in request.GET:
        struct = request.GET['struct']
    else:
        return redirect('unknown')

    if 'type' in request.GET:
        type = request.GET['type']
    else:
        return redirect('unknown')
    if 'id' in request.GET and 'validation' in request.GET:
        id = request.GET['id']
        validation = request.GET['validation']
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

    if int(validation) == 0:
        validate = 'validated'
    elif int(validation) == 1:
        validate = 'invalidated'

    # Connect to DB
    es = esActions.es_connector()

    # Get scope informations
    if type == "rsr":
        scope_param = esActions.scope_p("_id", id)

        res = es.search(index=struct + "-*-researchers", body=scope_param)
        try:
            entity = res['hits']['hits'][0]['_source']
        except:
            return redirect('unknown')

        index = struct + '-' + entity['labHalId'] + '-researchers'
        lab_index = struct + '-' + entity['labHalId'] + '-laboratories'

        # get tree from lab
        lab_scope_param = esActions.scope_p("_id", entity['labHalId'])

        res = es.search(index=struct + "*-laboratories", body=lab_scope_param)
        entity_lab = res['hits']['hits'][0]['_source']

        lab_tree = entity_lab['concepts']

        if request.method == 'POST':
            toInvalidate = request.POST.get("toInvalidate", "").split(",")

            for conceptId in toInvalidate:

                sid = conceptId.split('.')
                for children in entity['concepts']['children']:
                    if len(sid) >= 1:
                        if sid[0] == children['id']:
                            lab_tree = utils.appendToTree(children, entity, lab_tree, validate)
                            children['state'] = validate

                    if 'children' in children:
                        for children1 in children['children']:
                            if len(sid) >= 2:
                                if sid[0] + '.' + sid[1] == children1['id']:
                                    lab_tree = utils.appendToTree(children1, entity, lab_tree, validate)
                                    children1['state'] = validate

                            if 'children' in children1:
                                for children2 in children1['children']:
                                    if len(sid) >= 3:
                                        if sid[0] + '.' + sid[1] + '.' + sid[2] == children2['id']:
                                            lab_tree = utils.appendToTree(children2, entity, lab_tree, validate)
                                            children2['state'] = validate

            es.update(index=index, refresh='wait_for', id=entity['ldapId'],
                      body={"doc": {"concepts": entity['concepts']}})

            es.update(index=lab_index, refresh='wait_for', id=entity['labHalId'],
                      body={"doc": {"concepts": lab_tree}})

    return redirect('/check/?struct=' + struct + '&type=' + type + '&id=' + id + '&from=' + dateFrom + '&to=' + dateTo + '&data=' + data
                    + '&validation=' + validation)


def validate_credentials(request):
    # Get parameters
    if 'struct' in request.GET:
        struct = request.GET['struct']
    else:
        return redirect('unknown')

    if 'type' in request.GET and 'id' in request.GET:
        type = request.GET['type']
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
    es = esActions.es_connector()

    if request.method == 'POST':

        if type == "rsr":
            idRef = request.POST.get("f_IdRef")
            orcId = request.POST.get("f_orcId")
            function = request.POST.get("f_status")

            scope_param = esActions.scope_p("_id", id)

            res = es.search(index=struct + "*-researchers", body=scope_param)
            try:
                entity = res['hits']['hits'][0]['_source']
            except:
                return redirect('unknown')

            print(struct + "-" + entity['labHalId'] + '-researchers')

            es.update(index=struct + "-" + entity['labHalId'] + '-researchers', refresh='wait_for', id=id,
                      body={"doc": {"idRef": idRef, "orcId": orcId, "validated": True, "function": function}})

        if type == "lab":
            rsnr = request.POST.get("f_rsnr")
            idRef = request.POST.get("f_IdRef")

            es.update(index=struct + "-" + id + "-laboratories", refresh='wait_for', id=id,
                      body={"doc": {"rsnr": rsnr, "idRef": idRef, "validated": True}})

    return redirect('/check/?struct=' + struct + '&type=' + type + '&id=' + id + '&from=' + dateFrom + '&to=' + dateTo + '&data=' + data)


def validate_guiding_keywords(request):
    # Get parameters
    if 'struct' in request.GET:
        struct = request.GET['struct']
    else:
        return redirect('unknown')

    if 'type' in request.GET and 'id' in request.GET:
        type = request.GET['type']
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
    es = esActions.es_connector()

    if request.method == 'POST':

        guidingKeywords = request.POST.get("f_guidingKeywords").split(";")

        if type == "rsr":
            scope_param = esActions.scope_p("_id", id)

            res = es.search(index=struct + "*-researchers", body=scope_param)
            try:
                entity = res['hits']['hits'][0]['_source']
            except:
                return redirect('unknown')

            es.update(index=struct + "-" + entity['labHalId'] + "-researchers", refresh='wait_for', id=id,
                      body={"doc": {"guidingKeywords": guidingKeywords}})

        if type == "lab":
            es.update(index=struct + "-" + str(id) + "-laboratories", refresh='wait_for', id=id,
                      body={"doc": {"guidingKeywords": guidingKeywords}})

    return redirect('/check/?struct=' + struct + '&type=' + type + '&id=' + id + '&from=' + dateFrom + '&to=' + dateTo + '&data=' + data)


def validate_research_description(request):
    # Get parameters
    if 'struct' in request.GET:
        struct = request.GET['struct']
    else:
        return redirect('unknown')

    if 'type' in request.GET and 'id' in request.GET:
        type = request.GET['type']
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
    es = esActions.es_connector()

    if request.method == 'POST':

        research_summary = request.POST.get("f_research_summary")
        research_projectsInProgress = request.POST.get("f_research_projectsInProgress")
        research_projectsAndFundings = request.POST.get("f_research_projectsAndFundings")

        soup = BeautifulSoup(research_summary, 'html.parser')
        research_summary_raw = soup.getText().replace("\n", " ")

        soup = BeautifulSoup(research_projectsInProgress, 'html.parser')
        research_projectsInProgress_raw = soup.getText().replace("\n", " ")

        soup = BeautifulSoup(research_projectsAndFundings, 'html.parser')
        research_projectsAndFundings_raw = soup.getText().replace("\n", " ")

        if type == "rsr":
            scope_param = esActions.scope_p("_id", id)

            res = es.search(index=struct + "*-researchers", body=scope_param)
            try:
                entity = res['hits']['hits'][0]['_source']
            except:
                return redirect('unknown')

            es.update(index=struct + "-" + entity['labHalId'] + "-researchers", refresh='wait_for', id=id,
                      body={"doc": {"research_summary": research_summary, "research_summary_raw": research_summary_raw,
                                    "research_projectsInProgress": research_projectsInProgress,
                                    "research_projectsInProgress_raw": research_projectsInProgress_raw,
                                    "research_projectsAndFundings": research_projectsAndFundings,
                                    "research_projectsAndFundings_raw": research_projectsAndFundings_raw,
                                    "research_updatedDate": datetime.today().isoformat()
                                    }})

    return redirect('/check/?struct=' + struct + '&type=' + type + '&id=' + id + '&from=' + dateFrom + '&to=' + dateTo + '&data=' + data)


def refresh_aurehal_id(request):
    # Get parameters
    if 'struct' in request.GET:
        struct = request.GET['struct']
    else:
        return redirect('unknown')

    if 'type' in request.GET and 'id' in request.GET:
        type = request.GET['type']
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
    es = esActions.es_connector()

    scope_param = esActions.scope_p("_id", id)

    res = es.search(index=struct + "*-researchers", body=scope_param)
    try:
        entity = res['hits']['hits'][0]['_source']
    except:
        return redirect('unknown')

    aurehalId = libsElastichal.getAureHal(entity['halId_s'])
    concepts = []
    if aurehalId != -1:
        archivesOuvertesData = getConceptsAndKeywords(aurehalId)
        concepts = utils.filterConcepts(archivesOuvertesData['concepts'], validated_ids=[])

    es.update(index=struct + "-" + entity['labHalId'] + "-researchers", refresh='wait_for', id=id,
              body={"doc": {"aurehalId": aurehalId, 'concepts': concepts}})

    return redirect('/check/?struct=' + struct + '&type=' + type + '&id=' + id + '&from=' + dateFrom + '&to=' + dateTo + '&data=' + data)


def force_update_references(request):
    # Get parameters
    if 'struct' in request.GET:
        struct = request.GET['struct']
    else:
        return redirect('unknown')

    if 'type' in request.GET:
        type = request.GET['type']
    else:
        return redirect('unknown')

    if 'id' in request.GET:
        id = request.GET['id']
    else:
        return redirect('unknown')

    if 'from' in request.GET:
        dateFrom = request.GET['from']
    if 'to' in request.GET:
        dateTo = request.GET['to']

    if 'validation' in request.GET:
        validation = request.GET['validation']

    # Connect to DB
    es = esActions.es_connector()

    # if request.method == 'POST':
    # comprend pas pourquoi cette ligne d'autant qu'on récupère les paramètres sur GET....

    if type == "rsr":
        scope_param = esActions.scope_p("_id", id)

        res = es.search(index=struct + "*-researchers", body=scope_param)
        try:
            entity = res['hits']['hits'][0]['_source']
        except:
            return redirect('unknown')
        collecte_docs(entity)

    return redirect(
        '/check/?struct=' + struct + '&type=' + type + '&id=' + id + '&from=' + dateFrom + '&to=' + dateTo + '&data=references' + '&validation='
        + validation)


def update_members(request):
    # Get parameters
    if 'struct' in request.GET:
        struct = request.GET['struct']
    else:
        return redirect('unknown')

    if 'type' in request.GET and 'id' in request.GET:
        type = request.GET['type']
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
    es = esActions.es_connector()

    if request.method == 'POST':
        toUpdate = request.POST.get("toUpdate", "").split(",")

        for element in toUpdate:
            element = element.split(":")
            scope_param = esActions.scope_p("_id", element[0])

            # attention multi univ la...
            res = es.search(index="*-researchers", body=scope_param)
            try:
                entity = res['hits']['hits'][0]['_source']
            except:
                return redirect(
                    '/check/?struct=' + struct + '&type=' + type + '&id=' + id + '&from=' + dateFrom + '&to=' + dateTo + '&data=' + data)
            es.update(index=res['hits']['hits'][0]['_index'],
                      refresh='wait_for', id=entity['ldapId'],
                      body={"doc": {"axis": element[1]}})

    return redirect(
        '/check/?struct=' + struct + '&type=' + type + '&id=' + id + '&from=' + dateFrom + '&to=' + dateTo + '&data=' + data)


def update_authorship(request):
    # Get parameters
    if 'struct' in request.GET:
        struct = request.GET['struct']
    else:
        return redirect('unknown')

    if 'type' in request.GET and 'id' in request.GET:
        type = request.GET['type']
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
    es = esActions.es_connector()

    scope_param = esActions.scope_p("ldapId", id)

    res = es.search(index=struct + "-" + "*" + "-researchers", body=scope_param)
    try:
        entity = res['hits']['hits'][0]['_source']
    except:
        return redirect('unknown')

    try:
        toProcess = json.loads(request.POST.get("toProcess", ""))

        for doc in toProcess:

            # update in researcher's collection
            field = "_id"
            doc_param = esActions.scope_p(field, doc["docid"])

            res = es.search(index=struct + "-" + entity["labHalId"] + "-researchers-" + entity["ldapId"] + "-documents",
                            body=doc_param)

            if len(res['hits']['hits']) > 0:
                if "autorship" in res['hits']['hits'][0]['_source']:
                    authorship = res['hits']['hits'][0]['_source']["authorship"]
                    exists = False
                    for author in authorship:
                        if author["halId_s"] == entity["halId_s"]:
                            exists = True
                            author["authorship"] = doc["authorship"]
                    if not exists:
                        authorship.append({"authorship": doc["authorship"], "halId_s": entity['halId_s']})
                else:
                    authorship = [
                        {"authorship": doc["authorship"], "halId_s": entity['halId_s']}
                    ]
            else:
                authorship = [
                    {"authorship": doc["authorship"], "halId_s": entity['halId_s']}
                ]

            es.update(index=struct + '-' + entity['labHalId'] + "-researchers-" + entity["ldapId"] + '-documents',
                      refresh='wait_for', id=doc['docid'],
                      body={"doc": {"authorship": authorship}})

            # update in laboratory's collection
            field = "_id"
            doc_param = esActions.scope_p(field, doc["docid"])

            res = es.search(index=struct + "-" + entity["labHalId"] + "-laboratories-documents",
                            body=doc_param)

            try:
                if len(res['hits']['hits']) > 0:
                    if "autorship" in res['hits']['hits'][0]['_source']:
                        authorship = res['hits']['hits'][0]['_source']["authorship"]
                        exists = False
                        for author in authorship:
                            if author["halId_s"] == entity["halId_s"]:
                                exists = True
                                author["authorship"] = doc["authorship"]
                        if not exists:
                            authorship.append({"authorship": doc["authorship"], "halId_s": entity['halId_s']})
                    else:
                        authorship = [
                            {"authorship": doc["authorship"], "halId_s": entity['halId_s']}
                        ]
                else:
                    authorship = [
                        {"authorship": doc["authorship"], "halId_s": entity['halId_s']}
                    ]

                es.update(index=struct + '-' + entity['labHalId'] + "-laboratories-documents",
                          refresh='wait_for', id=doc['docid'],
                          body={"doc": {"authorship": authorship}})
            except:
                print("docid " + str(doc["docid"]) + " non trouvé dans l'index des labs...")
    except:
        pass

    return redirect(
        '/check/?struct=' + struct + '&type=' + type + '&id=' + id + '&from=' + dateFrom + '&to=' + dateTo + '&data=' + data + "&validation=1")


def export_hceres_xls(request):
    # Get parameters
    if 'struct' in request.GET:
        struct = request.GET['struct']
    else:
        return redirect('unknown')

    if 'type' in request.GET and 'id' in request.GET:
        type = request.GET['type']
        id = request.GET['id']
    else:
        return redirect('unknown')

    scope_param = esActions.scope_p("halStructId", id)

    key = "halStructId"
    ext_key = "harvested_from_ids"

    es = esActions.es_connector()

    res = es.search(index=struct + "-" + id + "-laboratories", body=scope_param)
    try:
        entity = res['hits']['hits'][0]['_source']
    except:
        return redirect('unknown')

    # Acquisition des chercheurs à traiter
    # toProcess = json.loads(request.POST.get("toProcess", ""))
    # toProcess_extra_cleaned = []
    # toProcess_extra = request.POST.get("toProcess_extra", "").splitlines()
    # for line in toProcess_extra:
    #     values = line.split(";")
    #     toProcess_extra_cleaned.append({"halId": values[0], "axis": values[1], "function": values[2], "scope": values[3]})
    #
    # toProcess.extend(toProcess_extra_cleaned)
    scope_bool_type = "filter"
    validate = True
    date_range_type = "publicationDate_tdate"
    dateFrom = "2016-01-01"
    dateTo = "2021-12-31"
    ref_param = esActions.ref_p(scope_bool_type, ext_key, entity[key], validate, date_range_type, dateFrom, dateTo)

    count = es.count(index=struct + "-" + entity["halStructId"] + "-laboratories-documents", body=ref_param)['count']
    print(struct + "-" + entity["halStructId"] + "-laboratories-documents")
    print(count)
    references = es.search(index=struct + "-" + entity["halStructId"] + "-laboratories-documents", body=ref_param,
                           size=count)

    from .libs import hceres

    references_cleaned = []

    for ref in references['hits']['hits']:
        references_cleaned.append(ref['_source'])

    sort_results = hceres.sortReferences(references_cleaned, entity["halStructId"])

    art_df = sort_results[0]
    book_df = sort_results[1]
    conf_df = sort_results[2]
    hdr_df = sort_results[3]

    art_df = art_df.fillna("")
    book_df = book_df.fillna("")
    conf_df = conf_df.fillna("")
    hdr_df = hdr_df.fillna("")

    if not (conf_df.columns == 'doiId_s').any():
        conf_df["doiId_s"] = " "
    if not (hdr_df.columns == 'defenseDateY_i').any():
        hdr_df["defenseDateY_i"] = " "
    if not (book_df.columns == 'isbn_s').any():
        book_df["isbn_s"] = ""

    output = IO()

    writer = pd.ExcelWriter(output, engine='openpyxl')
    if len(art_df.index) > 0:
        art_df[['authfullName_s', 'title_s', 'journalTitle_s', 'volFull_s', 'page_s', 'publicationDateY_i', 'doiId_s',
                'team', 'hasPhDCandidate', 'hasAuthorship', 'openAccess_bool_s']].to_excel(writer, 'ART', index=False)
    else:
        art_df.to_excel(writer, 'ART', index=False)
    if len(book_df.index) > 0:
        book_df[['authfullName_s', 'title_s', 'journalTitle_s', 'volFull_s', 'page_s', 'publicationDateY_i', 'isbn_s',
                 'team', 'hasPhDCandidate', 'hasAuthorship', 'openAccess_bool_s']].to_excel(writer, 'OUV', index=False)
    else:
        book_df.to_excel(writer, 'OUV', index=False)
    if len(conf_df.index) > 0:
        if  'page_s' in (conf_df):
            conf_df[['authfullName_s', 'title_s', 'journalTitle_s', 'volFull_s', 'page_s', 'publicationDateY_i', 'doiId_s',
                 'team', 'conferenceTitle_s', 'conferenceDate_s', 'hasPhDCandidate', 'hasAuthorship',
                 'openAccess_bool_s']].to_excel(writer, 'CONF',
                                                index=False)
        else:
            conf_df[['authfullName_s', 'title_s', 'journalTitle_s', 'volFull_s', 'publicationDateY_i', 'doiId_s',
                 'team', 'conferenceTitle_s', 'conferenceDate_s', 'hasPhDCandidate', 'hasAuthorship',
                 'openAccess_bool_s']].to_excel(writer, 'CONF',
                                                index=False)
    else:
        conf_df.to_excel(writer, 'CONF', index=False)
    if len(hdr_df.index) > 0:
        hdr_df[['authfullName_s', 'defenseDateY_i', 'team']].to_excel(writer, 'HDR', index=False)
    else:
        hdr_df.to_excel(writer, 'HDR', index=False)
    writer.close()

    output.seek(0)

    filename = 'hceres_' + entity["acronym"] + '.xlsx'
    response = HttpResponse(
        output,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=%s' % filename

    return response


def idhal_checkout(idhal):
    confirmation = ""
    # idhal = "luc-quoniam" valeur test
    html = "https://api.archives-ouvertes.fr/search/?q=authIdHal_s:" + idhal
    response = urlopen(html)

    data_json = json.loads(response.read())

    print(data_json)
    print(data_json["response"]["numFound"])
    if data_json["response"]["numFound"] == 0:
        confirmation = 0
    else:
        confirmation = 1
    return confirmation


def cohesion(struct, id, dateFrom, dateTo):

    es = esActions.es_connector()

    # parametres fixes pour la recherche dans les bases Elastic
    scope_bool_type = "filter"
    scope_field = "harvested_from_ids"
    validate = True
    date_range_type = "submittedDate_tdate"

    # /

    # Récupére les infos sur le labo

    scope_param = esActions.scope_p("halStructId", id)

    res = es.search(index=struct + "-" + id + "-laboratories", body=scope_param)

    entity = res['hits']['hits'][0]['_source']

    # récupere les infos sur les chercheurs attachés au laboratoire
    field = "labHalId"
    rsr_param = esActions.scope_p(field, id)

    count = es.count(index="*-researchers", body=rsr_param)['count']

    rsrs = es.search(index="*-researchers", body=rsr_param, size=count)
    rsrs_cleaned = []

    for result in rsrs['hits']['hits']:
        rsrs_cleaned.append(result['_source'])

    ref_param = esActions.ref_p(scope_bool_type, scope_field, id, validate, date_range_type, dateFrom, dateTo)

    count = es.count(index=struct + "-" + id + "-laboratories-documents", body=ref_param)['count']
    print('Count of laboratory listed documents validated:')
    print(count)
    # references = es.search(index=struct + "-" + entity["halStructId"] + "-laboratories-documents", body=ref_param,size=count)

    cohesionvalues = []
    labtotalcount = 0
    searchertotalcount = 0

    for x in range(len(rsrs_cleaned)):
        ldapId = rsrs_cleaned[x]['ldapId']
        halId_s = rsrs_cleaned[x]['halId_s']
        structSirene = rsrs_cleaned[x]['structSirene']
        name = rsrs_cleaned[x]['name']
        validated = rsrs_cleaned[x]['validated']

        # nombre de documents avec le nom de l'auteur coté lab par ex: (authIdHal_s : david-reymond)
        ref_lab = esActions.ref_p(scope_bool_type, 'authIdHal_s', halId_s, validate, date_range_type, dateFrom, dateTo)
        raw_lab_doc_count = es.count(index=structSirene + "-" + id + "-laboratories-documents", body=ref_lab)['count']


        labtotalcount += raw_lab_doc_count

        # nombre de documents de l'auteur dans son index
        ref_param = esActions.ref_p(scope_bool_type, scope_field, halId_s, validate, date_range_type, dateFrom, dateTo)
        raw_searcher_doc_count = \
        es.count(index=structSirene + "-" + id + "-researchers-" + ldapId + "-documents", body=ref_param)['count']
        searchertotalcount += raw_searcher_doc_count
        # raw_searcher_doc_ref = es.search(index=struct + "-" + entity["halStructId"] + "-researchers-" + ldapId + "-documents", body=ref_param)['count']

        # création du dict à rajouter dans la liste
        profiledict = {"name": name, "ldapId": ldapId, "validated": validated, "labcount": raw_lab_doc_count,
                       "searchercount": raw_searcher_doc_count}

        # rajout à la liste
        cohesionvalues.append(profiledict)

    return cohesionvalues