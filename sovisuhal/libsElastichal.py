#import requests
import re
from unidecode import unidecode
import lxml.etree
from SPARQLWrapper import SPARQLWrapper, JSON
import requests
from bs4 import BeautifulSoup
from .libs import hal
import time

def convertIdHalToStr(idHal_i):
    res = requests.get('https://aurehal.archives-ouvertes.fr/author/browse?critere=idHal_i:"' + idHal_i + '"')
    soup = BeautifulSoup(res.text, 'html.parser')
    return soup.find("td", text="idHal_s").find_next_sibling("td").text.split()[0]

def getAureHal(idHal):

    print(idHal)

    sparql = SPARQLWrapper("http://sparql.archives-ouvertes.fr/sparql")
    sparql.setReturnFormat(JSON)

    sparql.setQuery("""
        select ?p ?o
        where  {
        <https://data.archives-ouvertes.fr/author/%s> ?p ?o
        }""" % idHal)
    results = sparql.query().convert()

    aureHal = [truc for truc in results['results']['bindings'] if
               truc['p']['value'] == "http://www.openarchives.org/ore/terms/aggregates"]

    ret_aureHal = -1

    for id in aureHal:
        print(id['o']['value'])
        res = requests.get(id['o']['value'])

        if 'Ressource inexistante' not in res.text:
            ret_aureHal = id['o']['value'].split('/')[-1]

    return ret_aureHal


def findIdRef(name):
    r = requests.post('https://www.idref.fr/Sru/Solr?q=persname_t:(' + name + ')&wt=json&sort=score%20desc&version=2.2&start=0&rows=30&indent=on&fl=id,persname_t,ppn_z,geogname_t,recordtype_z,affcourt_')

    if r.status_code == 200:
        data = r.json()

        if data['response']['numFound'] > 0:
            for result in data['response']['docs'][0:1]:
                return {'idRef': result['ppn_z'], 'score': 0}

    return {}


def normalizeName(keyword, type):
    if type == 'id':
        key = 'ppn_z'
    else:
        key = 'persname_t'

    r = requests.post(
        'https://www.idref.fr/Sru/Solr?q=' + key + ':(' + keyword + ')&wt=json&sort=score%20desc&version=2.2&start=0&rows=30&indent=on&fl=id,persname_t,ppn_z,geogname_t,recordtype_z,affcourt_')

    if r.status_code == 200:
        data = r.json()

        if data['response']['numFound'] > 0:
            for result in data['response']['docs'][0:1]:
                return re.sub("[\(\[].*?[\)\]]", "", result['persname_t'][0])

    return {}


def findNotice(idRef):
    r = requests.get('https://www.idref.fr/' + idRef + '.xml', stream=True)
    doc = lxml.etree.parse(r.raw)

    idHal_s = None
    idHal_i = None

    datafield = doc.xpath("//datafield[subfield='HAL']")

    print(datafield)

    for record in datafield:
        for x in record.xpath("./subfield[@code='a']"):
            idHal_s = x.text
        for x in record.xpath("./subfield[@code='d']"):
            idHal_i = x.text

    if idHal_i and idHal_s:
        return {'idHal_i': idHal_i, 'idHal_s': idHal_s, 'score': 0}
    elif idHal_i:
        return {'idHal_i': idHal_i, 'score': 0}
    elif idHal_s:
        return {'idHal_s': idHal_s, 'score': 0}
    else:
        return {}
