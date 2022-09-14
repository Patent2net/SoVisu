from elasticsearch import Elasticsearch
from elasticsearch import helpers

from datetime import datetime
import json



def es_connector(mode=True):
    if mode == "Prod":

        # secret = config('ELASTIC_PASSWORD')
        # context = create_ssl_context(cafile="../../stackELK/secrets/certs/ca/ca.crt")
        es = Elasticsearch('localhost',
                           http_auth=('elastic', secret),
                           scheme="http",
                           port=9200,
                           # ssl_context=context,
                           timeout=10)
    else:

        #es = Elasticsearch([{'host': 'localhost', scheme:"http", 'port': 9200}])
        es = Elasticsearch('http://localhost:9200')
        #es = Elasticsearch(hosts = ['http://localhost:9200', 'http://elastichal2:9200', 'http://elastichal3:9200',                 'http://elastichal1:9200'])
        es.options(request_timeout=100, retry_on_timeout= True, max_retries=3 )
    return es


def scope_all():
    scope = {
        "query": {
            "match_all": {}
        }
    }
    return scope


# Use that base code in other files to use scope_p function: variable_name = esActions.scope_p(scope_field, scope_value)
def scope_p(scope_field, scope_value):
    scope = {
        "query": {
            "match": {
                scope_field: scope_value
            }
        }
    }
    return scope


es = es_connector()

# Memo des pbs.
# Choix fait de se poser sur le ldapid --> pas de gestion des doublons type ex-doctorants
# si deux meme ldapid dans des index chercheurs différents alors
# memo du plus recent created seulement
scope_param = scope_all()
count = es.count(index="*-researchers")['count']
res = es.search(index="*-researchers", size=count)
chercheurs = res['hits']['hits']

docmap = {
    "properties": {
        "docid": {
            "type": "long"
        },
        "en_abstract_s": {
            "type": "text",  # formerly "string"
            "fields": {
                "keyword": {
                    "type": "keyword",
                    "ignore_above": 5000
                }}
        },
        "fr_abstract_s": {
            "type": "text",  # formerly "string"
            "fields": {
                "keyword": {
                    "type": "keyword",
                    "ignore_above": 5000
                }}
        },
        "it_abstract_s": {
            "type": "text",  # formerly "string"
            "fields": {
                "keyword": {
                    "type": "keyword",
                    "ignore_above": 5000
                }}
        },
        "es_abstract_s": {
            "type": "text",  # formerly "string"
            "fields": {
                "keyword": {
                    "type": "keyword",
                    "ignore_above": 5000
                }}
        },
        "pt_abstract_s": {
            "type": "text",  # formerly "string"
            "fields": {
                "keyword": {
                    "type": "keyword",
                    "ignore_above": 5000
                }}
        }
    }
}

for ind, doudou in enumerate(chercheurs):
    decoup = doudou['_index']  .split("-")
    structu = decoup [0]
    labo = decoup [1]
    idxDocs = structu + "-" + labo + "-researchers-"+ doudou['_id']  +"-documents"
    mapping = es.indices.get_mapping(index=idxDocs)
    if len(mapping.body[idxDocs]['mappings'])>0 and mapping.body[idxDocs]['mappings']['properties']['docid']['type'] != 'long':
        compte = es.count(index=idxDocs)['count']
        docs = es.search(index=idxDocs, size=compte)
        if len(docs["hits"]['hits']) >0:
            docu = docs["hits"]['hits']
            print(len(docu)," docs. Destruction de :", idxDocs)
            es.options(ignore_status=[400, 404]).indices.delete(index=idxDocs)
            dico = dict()
            dico['mappings'] = docmap
            dico['index'] = idxDocs
            es.indices.create(**dico)
            for doc in docu:
                doc ['_source']["docid"] = int(doc ['_source']["docid"] )
                es.index(index=idxDocs,
                          id=doc['_id'],
                          document=doc ["_source"])
            es.indices.refresh(index=idxDocs)
            #resp = es.indices.put_mapping(index=idxDocs, body=docmap)
    else:
        resp = es.indices.put_mapping(index=idxDocs, body=docmap)
        es.indices.refresh(index=idxDocs)

    print(resp)

print ("Traitement des collections labo")

count = es.count(index="*-laboratories", body=scope_param)['count']
res = es.search(index="*-laboratories", body=scope_param, size=count)
labos = res['hits']['hits']
for ind, lab in enumerate(labos):
    decoup = lab['_index']  .split("-")
    structu = decoup [0]
    labo = decoup [1]
    idxDocs = structu + "-" + labo + "-laboratories-documents"
    resp = es.indices.put_mapping(
        index=idxDocs, body=docmap)
    print(resp)