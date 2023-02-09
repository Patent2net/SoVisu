from sovisuhal.libs import esActions

es = esActions.es_connector()

scope_param = esActions.scope_all()

StructCount = es.count(index="*-structures", body=scope_param, request_timeout=50)[
    "count"
]
if StructCount > 0:
    Struct = es.search(index="*-structures", body=scope_param, size=StructCount)
    Struct = Struct["hits"]["hits"]


count = es.count(index="*-laboratories", body=scope_param, request_timeout=50)["count"]
if count > 0:
    Labo = es.search(index="*-laboratories", body=scope_param, size=count)
    Labo = Labo["hits"]["hits"]
    for doc in Labo:
        print(doc["_source"]["structSirene"])
        if "structAcronym" not in doc["_source"]:
            for doc_struct in Struct:
                if (
                    doc_struct["_source"]["structSirene"]
                    == doc["_source"]["structSirene"]
                ):
                    structAcronym = doc_struct["_source"]["acronym"]
                    print(doc["_index"])
                    es.update(
                        index=doc["_index"],
                        refresh="wait_for",
                        id=doc["_source"]["halStructId"],
                        body={"doc": {"structAcronym": structAcronym}},
                    )
                    print(
                        f"le champ structAcronym: {structAcronym} a été rajouté a {doc['_index']}"
                    )
        else:
            print(f"le champ structAcronym existe dans {doc['_index']}")
