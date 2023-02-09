from elasticsearch import Elasticsearch
from elasticsearch import helpers

from datetime import datetime
import json


# Custom libs
# from sovisuhal.libs import esActions
# from elasticHal.libs import archivesOuvertes, utils

# Connect to DB


def es_connector(mode=True):
    if mode == "Prod":
        # secret = config('ELASTIC_PASSWORD')
        # context = create_ssl_context(cafile="../../stackELK/secrets/certs/ca/ca.crt")
        es = Elasticsearch(
            "localhost",
            http_auth=("elastic", secret),
            scheme="http",
            port=9200,
            # ssl_context=context,
            timeout=10,
        )
    else:
        # es = Elasticsearch([{'host': 'localhost', scheme:"http", 'port': 9200}])
        # es = Elasticsearch('http://localhost:9200')
        es = Elasticsearch(
            hosts=[
                "http://localhost:9200",
                "http://elastichal2:9200",
                "http://elastichal3:9200",
                "http://elastichal1:9200",
            ]
        )
        es.options(request_timeout=100, retry_on_timeout=True, max_retries=3)
    return es


def scope_all():
    scope = {"query": {"match_all": {}}}
    return scope


# Use that base code in other files to use scope_p function: variable_name = esActions.scope_p(scope_field, scope_value)
def scope_p(scope_field, scope_value):
    scope = {"query": {"match": {scope_field: scope_value}}}
    return scope


es = es_connector()

# Memo des pbs.
# Choix fait de se poser sur le ldapid --> pas de gestion des doublons type ex-doctorants
# si deux meme ldapid dans des index chercheurs différents alors
# memo du plus recent created seulement
scope_param = scope_all()
count = es.count(index="*-researchers", body=scope_param)["count"]
res = es.search(index="*-researchers", body=scope_param, size=count)
chercheurs = res["hits"]["hits"]

docmap = {
    "properties": {
        "docid": {"type": "long"},
        "en_abstract_s": {
            "type": "text",  # formerly "string"
            "fields": {"keyword": {"type": "keyword", "ignore_above": 5000}},
        },
        "fr_abstract_s": {
            "type": "text",  # formerly "string"
            "fields": {"keyword": {"type": "keyword", "ignore_above": 5000}},
        },
        "it_abstract_s": {
            "type": "text",  # formerly "string"
            "fields": {"keyword": {"type": "keyword", "ignore_above": 5000}},
        },
        "es_abstract_s": {
            "type": "text",  # formerly "string"
            "fields": {"keyword": {"type": "keyword", "ignore_above": 5000}},
        },
        "pt_abstract_s": {
            "type": "text",  # formerly "string"
            "fields": {"keyword": {"type": "keyword", "ignore_above": 5000}},
        },
    }
}

for ind, doudou in enumerate(chercheurs):
    decoup = doudou["_index"].split("-")
    structu = decoup[0]
    labo = decoup[1]
    idxDocs = structu + "-" + labo + "-researchers-" + doudou["_id"] + "-documents"
    try:
        compte = es.count(index=idxDocs, body=scope_param)["count"]
        docs = es.search(index=idxDocs, body=scope_param, size=compte)
        if len(docs["hits"]["hits"]) > 0:
            docu = docs["hits"]["hits"]
            print(len(docu), " docs. Destruction de :", idxDocs)
            # ids = [doc ['_id'] for doc in docu]
            # for idIndex in ids:
            #     es.delete(index=idxDocs, id=idIndex)

            es.options(ignore_status=[400, 404]).indices.delete(index=idxDocs)
            print("recreation")
            dico = dict()
            dico["mappings"] = docmap
            dico["index"] = idxDocs
            es.indices.create(**dico)
            # settings ={ # au cas où
            #     # Put your index settings here
            #     # Example: "index.mapping.total_fields.limit": 100000
            # })
            print("integration mapping")
            print("màj avec ", len(docu), "docs")
            # for doc in docu:
            #     es.index(index=idxDocs,
            #           id=doc['_id'],
            #           document=doc ["_source"],
            #         mapping=docmap)
            # es.update(index=idxDocs,
            #           id=doudou['_id'],
            #           body=json.dumps(docu))
            if len(docu) > 50:
                for indi in range(int(len(docu) // 50) + 1):
                    boutdeDoc = docu[indi * 50 : indi * 50 + 50]
                    helpers.bulk(es, boutdeDoc, index=idxDocs)
            else:
                for doc in docu:
                    es.index(index=idxDocs, id=doc["_id"], document=doc["_source"])
            es.indices.refresh(index=idxDocs)
        else:
            print(
                "pas de docs associées pour : ",
                doudou["_id"],
                " index ",
                doudou["_index"],
            )
    except:
        print("erreur pour : ", idxDocs)

print("Traitement des collections labo")

count = es.count(index="*-laboratories", body=scope_param)["count"]
res = es.search(index="*-laboratories", body=scope_param, size=count)
labos = res["hits"]["hits"]
for ind, lab in enumerate(labos):
    decoup = lab["_index"].split("-")
    structu = decoup[0]
    labo = decoup[1]
    idxDocs = structu + "-" + labo + "-laboratories-documents"
    compte = es.count(index=idxDocs, body=scope_param)["count"]
    docs = es.search(index=idxDocs, body=scope_param, size=compte)
    if len(docs["hits"]["hits"]) > 0:
        docu = docs["hits"]["hits"]
        print("destruction de :", idxDocs)
        # ids = [doc ['_id'] for doc in docu]
        # for idIndex in ids:
        #     es.delete(index=idxDocs, id=idIndex)

        print("recreation")
        # es.indices.create(idxDocs)
        # settings
        # es.indices.put_settings(index=idxDocs, body={ # au cas où
        #     # Put your index settings here
        #     # Example: "index.mapping.total_fields.limit": 100000
        # })
        print("integration mapping")

        es.options(ignore_status=[400, 404]).indices.delete(index=idxDocs)
        print("recreation")
        dico = dict()
        dico["mappings"] = docmap
        dico["index"] = idxDocs
        es.indices.create(**dico)

        print("màj fr ", len(docu), " docs")
        if len(docu) > 0:
            for indi in range(int(len(docu) // 50) + 1):
                boutdeDoc = docu[indi * 50 : indi * 50 + 50]
                helpers.bulk(es, boutdeDoc, index=idxDocs)
        else:
            for doc in docu:
                es.index(index=idxDocs, id=doc["_id"], document=doc["_source"])

        es.indices.refresh(index=idxDocs)
    else:
        print("pas de docs associées pour : ", lab["_id"], " index ", lab["_index"])
