import requests
import random


def findPublications(idHal, field, increment=0):

    articles = []
    flags = 'docid,halId_s,labStructId_i,authIdHal_s,authIdHal_i,doiId_s,authFullName_s,doiId_s,journalIssn_s,' \
            'publicationDate_tdate,submittedDate_tdate,modifiedDate_tdate,producedDate_tdate,' \
            'fileMain_s,language_s,title_s,*_subTitle_s,*_abstract_s,*_keyword_s,label_bibtex,fulltext_t,' \
            'version_i,journalDate_s,journalTitle_s,journalPublisher_s,funding_s,' \
            'openAccess_bool,journalSherpaPostPrint_s,journalSherpaPrePrint_s,journalSherpaPostRest_s,journalSherpaPreRest_s'

    req = requests.get('http://api.archives-ouvertes.fr/search/?q=' + field + ':' + str(idHal) + '&fl=' + flags + '&start=' + str(increment))

    if req.status_code == 200:
        data = req.json()
        if "response" in data.keys():
            data = data['response']
            count = data['numFound']

            for article in data['docs']:
                articles.append(article)
            if (count > 30) and (increment < (count)):
                increment += 30
                tmp_articles = findPublications(idHal, field, increment=increment)
                for tmp_article in tmp_articles:
                    articles.append(tmp_article)
                return articles
            else:
                return articles
        else:
            print('Error : wrong response from HAL API endpoint')
            return -1
    else:
        print('Error : can not reach HAL API endpoint')
        return articles

def findRandomPublication(idHal, field):

    req = requests.get('http://api.archives-ouvertes.fr/search/?q=' + field + ':' + str(idHal))
    if req.status_code == 200:
        data = req.json()
        if "response" in data.keys():
            data = data['response']

            return random.choice(data['docs'])

    return -1