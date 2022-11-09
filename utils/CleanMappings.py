from elasticsearch import Elasticsearch
from elasticsearch import helpers

from datetime import datetime
import json
import time
import random


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
        es = Elasticsearch('http://localhost:9200', http_compress=True,  connections_per_node=50, request_timeout=200, retry_on_timeout=True
                           )
        #es = Elasticsearch(hosts = ['http://localhost:9200', 'http://elastichal2:9200', 'http://elastichal3:9200',                 'http://elastichal1:9200'])
        es.options(request_timeout=100, retry_on_timeout= True, max_retries=5).cluster.health(
            wait_for_no_initializing_shards=True,
            wait_for_no_relocating_shards=True,
            wait_for_status="green" # yellow doit pas forcément marcher si pas un cluster !
        )

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
            "type": "long",
            "fields": {
                "keyword": {
                    "type": "keyword",
                    "ignore_above": 512
                }}
        },
    "en_keyword_s": {
        "type": "text",
        "fields": {
          "keyword": {
            "type": "keyword",
            "ignore_above": 512
          }
        }
      },
    "en_keyword_s": {
        "type": "text",
        "fields": {
          "keyword": {
            "type": "keyword",
            "ignore_above": 512
          }
        }
      },
        "fr_entites": {
            "type": "text",
            "fields": {
                "keyword": {
                    "type": "keyword",
                    "ignore_above": 512
                }
            }
        },
        "en_entites": {
            "type": "text",
            "fields": {
                "keyword": {
                    "type": "keyword",
                    "ignore_above": 512
                }
            }
        },
    "fr_teeft_keywords": {
            "type": "text",  # formerly "string"
            "fields": {
                "keyword": {
                    "type": "keyword",
                    "ignore_above": 512
                }}
        },
    "en_teeft_keywords": {
            "type": "text",  # formerly "string"
            "fields": {
                "keyword": {
                    "type": "keyword",
                    "ignore_above": 512
                }}
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
    if es.indices.exists(index=idxDocs):
        mapping = es.indices.get_mapping(index=idxDocs)
        #time.sleep(int(random.random() * 10))
        compte = es.count(index=idxDocs)['count']
        docs = es.search(index=idxDocs, size=compte)
        doIt = sum([not isinstance(doc['_source']['docid'], int) for doc in docs["hits"]['hits']])
        if len(mapping.body[idxDocs]['mappings'])>0 and 'docid' in mapping.body[idxDocs]['mappings']['properties'] .keys():
            if mapping.body[idxDocs]['mappings']['properties']['docid']['type'] == 'long':
                doIt = True
            elif 'fields' in mapping.body[idxDocs]['mappings']['properties']['docid'].keys():
                if 'keyword' not in mapping.body[idxDocs]['mappings']['properties']['docid']['fields']:
                    doIt = True
                else:
                    doIt = True

            else:
                doIt = True
    else:
        doIt = False

    if doIt:
        #time.sleep(int(random.random() * 10))
        if len(docs["hits"]['hits']) >0:
            docu = docs["hits"]['hits']
            print(len(docu)," docs. Destruction de :", idxDocs)
            es.options(ignore_status=[400, 404]).indices.delete(index=idxDocs)
            dico = dict()
            dico['mappings'] = docmap
            dico['index'] = idxDocs
            es.indices.create(**dico)
            if len(docu) >10:
                for doc in docu:
                    doc['_source']["docid"] = int(doc['_source']["docid"])
                for indi in range(int(len(docu) // 50) + 1):
                    boutdeDoc = docu[indi * 50:indi * 50 + 50]

                    helpers.bulk(
                        es,
                        boutdeDoc,
                        index=idxDocs
                    )
                resp= str(len(docu)) + " indexés "
            else:
                for doc in docu:
                    doc ['_source']["docid"] = int(doc ['_source']["docid"] )
                    es.options(request_timeout=200, retry_on_timeout=True, max_retries=5).index(index=idxDocs,
                              id=doc['_id'],
                              document=doc ["_source"])
            resp=es.indices.refresh(index=idxDocs)
            print(es.cluster.health())

            es.indices.put_mapping(index=idxDocs, body=docmap)
        else:
            resp = "rien à faire : " + idxDocs
    else:
        if es.indices.exists(index=idxDocs):
            resp = es.indices.put_mapping(index=idxDocs, body=docmap)
            es.indices.refresh(index=idxDocs)
        else:
            pass # peut-être faudrait le créer vierge ?
            resp =("rien à faire")
    if doIt:
        print(resp, idxDocs)

print ("Traitement des collections labo")

count = es.count(index="*-laboratories")['count']
res = es.search(index="*-laboratories", size=count)
labos = res['hits']['hits']
for ind, lab in enumerate(labos):
    decoup = lab['_index']  .split("-")
    structu = decoup [0]
    labo = decoup [1]
    idxDocs = structu + "-" + labo + "-laboratories-documents"
    if es.indices.exists(index=idxDocs):
        mapping = es.indices.get_mapping(index=idxDocs)
        # time.sleep(int(random.random() * 10))
        compte = es.count(index=idxDocs)['count']
        docs = es.search(index=idxDocs, size=compte)
        doIt = sum([not isinstance(doc['_source']['docid'], int) for doc in docs["hits"]['hits']])
        if len(mapping.body[idxDocs]['mappings']) > 0 and 'docid' in mapping.body[idxDocs]['mappings'][
            'properties'].keys():
            if mapping.body[idxDocs]['mappings']['properties']['docid']['type'] == 'long':
                doIt = True
            elif 'fields' in mapping.body[idxDocs]['mappings']['properties']['docid'].keys():
                if 'keyword' not in mapping.body[idxDocs]['mappings']['properties']['docid']['fields']:
                    doIt = True
                else:
                    doIt = True

            else:
                doIt = True
    else:
        doIt = False

    if doIt:
        #
        if len(docs["hits"]['hits']) > 0:
            docu = docs["hits"]['hits']
            print(len(docu), " docs. Destruction de :", idxDocs)
            es.options(ignore_status=[400, 404]).indices.delete(index=idxDocs)
            dico = dict()
            dico['mappings'] = docmap
            dico['index'] = idxDocs
            es.indices.create(**dico)
            if len(docu) > 10:
                for doc in docu:
                    doc['_source']["docid"] = int(doc['_source']["docid"])
                for indi in range(int(len(docu) // 50) + 1):
                    boutdeDoc = docu[indi * 50:indi * 50 + 50]
                    helpers.parallel_bulk(
                        es,
                        boutdeDoc,
                        index=idxDocs
                    )
                    time.sleep(int(random.random() * 10))

            else:
                for doc in docu:
                    doc['_source']["docid"] = int(doc['_source']["docid"])
                    es.index(index=idxDocs,
                             id=doc['_id'],
                             document=doc["_source"],
                             timeout=300)
                    time.sleep(int(random.random() * 10))
            es.indices.refresh(index=idxDocs)
            es.cluster.health()

            # resp = es.indices.put_mapping(index=idxDocs, body=docmap)
    else:
        if es.indices.exists(index=idxDocs):
            resp = es.indices.put_mapping(index=idxDocs, body=docmap)
            es.indices.refresh(index=idxDocs)
        else:
            pass  # peut-être faudrait le créer vierge ?

