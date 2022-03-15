from nested_lookup import nested_lookup
import urllib.request
import re
import dateutil.parser
from datetime import datetime
from dateutil.relativedelta import relativedelta


def shouldBeOpen(doc):
    # -1 non
    # 1 oui
    # 0 no se
    # 2 déjà open

    if 'fileMain_s' not in doc:
        if 'journalSherpaPostPrint_s' in doc:
            if doc['journalSherpaPostPrint_s'] == 'can':
                return 1
            if doc['journalSherpaPostPrint_s'] == 'restricted':
                matches = re.finditer('(\S+\s+){2}(?=embargo)', doc['journalSherpaPostRest_s'].replace('[', ' '))
                max = 0

                for m in matches:

                    c = m.group().split(' ')[0]
                    if c.isnumeric():
                        # check if sometimes there is year but atm, nope
                        if int(c) > max:
                            max = int(c)

                pDate = dateutil.parser.parse(doc['publicationDate_tdate']).replace(tzinfo=None)
                currDate = datetime.now()
                diff = relativedelta(currDate, pDate)

                diffMonths = diff.years * 12 + diff.months
                if diffMonths > max:
                    return 1
                else:
                    return -1
            if doc['journalSherpaPostPrint_s'] == 'cannot':
                return -1
        return 0
    return 2


def calculateMDS(doc):
    score = 0

    if 'title_s' in doc:
        hasTitle = True
    else:
        hasTitle = False

    if 'doiId_s' in doc:
        hasDoi = True
    else:
        hasDoi = False

    if 'publicationDate_tdate' in doc:
        hasPublicationDate = True
    else:
        hasPublicationDate = False

    keywords = nested_lookup(
        key="_keyword_s",
        document=doc,
        wild=True,
        with_keys=True,
    )

    if len(keywords) > 0:
        hasKw = True
    else:
        hasKw = False

    abstracts = nested_lookup(
        key="_abstract_s",
        document=doc,
        wild=True,
        with_keys=True,
    )

    if len(abstracts) > 0:
        hasAbstract = True
    else:
        hasAbstract = False

    if 'fileMain_s' in doc:
        hasAttachedFile = True
    else:
        hasAttachedFile = False

    if hasTitle:
        score += 1 * 0.8
    if hasPublicationDate:
        score += 1 * 0.2
    if hasKw:
        score += 1 * 1
    if hasAbstract:
        score += 1 * 0.8
    if hasAttachedFile:
        score += 1 * 0.4
    if hasDoi:
        score += 1 * 0.6

    return score * 100 / (0.8 + 0.2 + 1 + 0.8 + 0.4 + 0.6)


def appendToTree(scope, rsr, tree, state):

    rsrData = {'ldapId': rsr['ldapId'], 'firstName': rsr['firstName'], 'lastName': rsr['lastName'], 'state': state}
    rsrId = rsr['ldapId']

    sid = scope['id'].split('.')

    print('llllll', end=' ')
    print(scope)

    scopeData = {'id': scope['id'], 'label_fr': scope['label_fr'], 'label_en': scope['label_en'],
                 'children': [],
                 'researchers': [
                     rsrData
                 ]}

    if len(sid) == 1:
        exists = False
        for child in tree['children']:
            if sid[0] == child['id']:
                if 'researchers' in child:
                    for rsr in child['researchers']:
                        rsrexists = False
                        if rsr['ldapId'] == rsrId:
                            rsr['state'] = state
                            rsrexists = True
                if not rsrexists:
                    child['researchers'].append(rsrData)
                exists = True
        if not exists:
            tree['children'].append(scopeData)

    if len(sid) == 2:
        exists = False
        for child in tree['children']:
            if sid[0] == child['id'] and 'children' in child:
                for child1 in child['children']:
                    if sid[0] + '.' + sid[1] == child1['id']:
                        if 'researchers' in child1:
                            for rsr in child1['researchers']:
                                rsrexists = False
                                if rsr['ldapId'] == rsrId:
                                    rsr['state'] = state
                                    rsrexists = True
                        if not rsrexists:
                            child1['researchers'].append(rsrData)
                        exists = True

        if not exists:
            for child in tree['children']:
                if 'children' in child and sid[0] == child['id']:
                    child['children'].append(scopeData)

    if len(sid) == 3:
        exists = False
        for child in tree['children']:
            if sid[0] == child['id'] and 'children' in child:
                for child1 in child['children']:
                    if sid[0] + '.' + sid[1] == child1['id'] and 'children' in child1:
                        for child2 in child1['children']:
                            if sid[0] + '.' + sid[1] + '.' + sid[2] == child2['id']:
                                if 'researchers' in child2:
                                    for rsr in child2['researchers']:
                                        rsrexists = False
                                        if rsr['ldapId'] == rsrId:
                                            rsr['state'] = state
                                            rsrexists = True
                                if not rsrexists:
                                    child2['researchers'].append(rsrData)
                                exists = True

        if not exists:
            for child in tree['children']:
                if 'children' in child and sid[0] == child['id']:
                    for child1 in child['children']:
                        if sid[0] + '.' + sid[1] == child1['id']:
                            child1['children'].append(scopeData)

    return tree


def filterConcepts(concepts, validated_ids):
    if len(concepts) > 0:

        for children in concepts['children']:
            if children['id'] in validated_ids:
                children['state'] = 'validated'
            if 'children' in children:
                for children1 in children['children']:
                    if children1['id'] in validated_ids:
                        children1['state'] = 'validated'
                    if 'children' in children1:
                        for children2 in children1['children']:
                            if children2['id'] in validated_ids:
                                children2['state'] = 'validated'

    return concepts
