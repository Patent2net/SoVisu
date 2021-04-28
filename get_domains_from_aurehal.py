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
    dom = {}
    dom['id'] = input.get('value')
    dom['label_en'] = getLabel(input.get('value'), 'en')
    dom['label_fr'] = getLabel(input.get('value'), 'fr')
    domains.append(dom)

print(domains)