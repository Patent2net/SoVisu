from elasticsearch import helpers

from sovisuhal.libs import esActions

# Connect to DB
es = esActions.es_connector()

# Memo des pbs.
# Choix fait de se poser sur le ldapid --> pas de gestion des doublons type ex-doctorants
# si deux meme ldapid dans des index chercheurs différents alors
# memo du plus recent created seulement
scope_param = esActions.scope_all()
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
                    boutdeDoc = docu[indi * 50: indi * 50 + 50]
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
    except IndexError:
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
                boutdeDoc = docu[indi * 50: indi * 50 + 50]
                helpers.bulk(es, boutdeDoc, index=idxDocs)
        else:
            for doc in docu:
                es.index(index=idxDocs, id=doc["_id"], document=doc["_source"])

        es.indices.refresh(index=idxDocs)
    else:
        print("pas de docs associées pour : ", lab["_id"], " index ", lab["_index"])
