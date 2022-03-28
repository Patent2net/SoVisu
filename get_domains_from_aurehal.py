import requests
from bs4 import BeautifulSoup
from SPARQLWrapper import SPARQLWrapper, JSON

sparql = SPARQLWrapper("http://sparql.archives-ouvertes.fr/sparql")
sparql.setReturnFormat(JSON)


def getLabel(topic, lang):
    sparql.setQuery("""
        select ?p ?o
        where  {
        <https://data.archives-ouvertes.fr/subject/%s> ?p ?o
        }""" % topic)
    results = sparql.query().convert()

    label = [truc['o']['value'] for truc in results['results']['bindings'] if
             truc['p']['value'] == "http://www.w3.org/2004/02/skos/core#prefLabel" if
             truc['o']['xml:lang'] == lang]

    return label[0]


r = requests.get('https://aurehal.archives-ouvertes.fr/domain/index')
soup = BeautifulSoup(r.text, 'html.parser')

tree = soup.find_all('ul', 'tree')
tree = tree[0]

inputs = tree.find_all('input')

domains = []

for input in inputs:
    dom = {'id': input.get('value'), 'label_en': getLabel(input.get('value'), 'en'),
           'label_fr': getLabel(input.get('value'), 'fr'), 'children': []}
    domains.append(dom)

tree = {'id': 'Concepts', 'children': []}

for dom in domains:
    sid = dom['id'].split('.')

    if len(sid) == 1:
        exists = False
        for child in tree['children']:
            if sid[0] == child['id']:
                exists = True
        if not exists:
            tree['children'].append(dom)

    if len(sid) == 2:
        exists = False
        for child in tree['children']:
            if sid[0] == child['id']:
                if 'children' in child:
                    for child1 in child['children']:
                        if sid[0] + '.' + sid[1] == child1['id']:
                            exists = True

        if not exists:
            for child in tree['children']:
                if 'children' in child:
                    if sid[0] == child['id']:
                        child['children'].append(dom)

    if len(sid) == 3:
        exists = False
        for child in tree['children']:
            if sid[0] == child['id']:
                if 'children' in child:
                    for child1 in child['children']:
                        if sid[0] + '.' + sid[1] == child1['id']:
                            if 'children' in child1:
                                for child2 in child1['children']:
                                    if sid[0] + '.' + sid[1] + '.' + sid[2] == child2['id']:
                                        exists = True

        if not exists:
            for child in tree['children']:
                if 'children' in child:
                    if sid[0] == child['id']:
                        for child1 in child['children']:
                            if sid[0] + '.' + sid[1] == child1['id']:
                                child1['children'].append(dom)


print(tree)
