from sovisuhal.libs import esActions


def return_struct():

    es = esActions.es_connector()

    scope_param = esActions.scope_all()

    StructCount = es.count(index="*-structures", body=scope_param, request_timeout=50)['count']
    if StructCount > 0:
        Struct = es.search(index="*-structures", body=scope_param, size=StructCount)
        Struct = Struct["hits"]["hits"]

    count = es.count(index="*-laboratories", body=scope_param, request_timeout=50)['count']
    if count > 0:
        Labos = es.search(index="*-laboratories", body=scope_param, size=count)
        Labos = Labos["hits"]["hits"]
        for labo in Labos:

            if 'structAcronym' not in labo['_source']:
                print(labo['_source']['acronym'])
                for doc_struct in Struct:
                    if doc_struct['_source']['structSirene'] == labo['_source']['structSirene']:
                        structAcronym = doc_struct['_source']['acronym']
                        print(labo['_index'])
                        es.update(index=labo['_index'], refresh='wait_for', id=labo['_source']['halStructId'], body={"doc": {"structAcronym": structAcronym}})
                        print(f"le champ structAcronym: {structAcronym} a été rajouté a {labo['_index']}")

                    else:
                        print("Warning: pas de structSirene")
                        print(labo['_index'])
                        es.update(index=labo['_index'], refresh='wait_for', id=labo['_source']['halStructId'], body={"doc": {"structAcronym": "Warning"}})
            else:
                print(f"le champ structAcronym existe dans {labo['_index']}")


def return_struct_from_index(index):
    # Cette fonction enregistre le struct Acronym d'un laboratoire en fonctions d'un index
    es = esActions.es_connector()

    scope_param = esActions.scope_all()

    StructCount = es.count(index="*-structures", body=scope_param, request_timeout=50)['count']
    if StructCount > 0:
        Struct = es.search(index="*-structures", body=scope_param, size=StructCount)
        Struct = Struct["hits"]["hits"]

    count = es.count(index=index, body=scope_param, request_timeout=50)['count']
    if count > 0:
        labo = es.search(index=index, body=scope_param, size=count)
        labo = labo["hits"]["hits"][0]
        if 'structAcronym' not in labo['_source']:
            print(labo['_source']['acronym'])
            for doc_struct in Struct:
                if doc_struct['_source']['structSirene'] == labo['_source']['structSirene']:
                    structAcronym = doc_struct['_source']['acronym']
                    print(labo['_index'])
                    es.update(index=labo['_index'], refresh='wait_for', id=labo['_source']['halStructId'], body={"doc": {"structAcronym": structAcronym}})
                    print(f"le champ structAcronym: {structAcronym} a été rajouté a {labo['_index']}")
                    return structAcronym

                else:
                    print("Warning: pas de structSirene")
                    print(labo['_index'])
                    es.update(index=labo['_index'], refresh='wait_for', id=labo['_source']['halStructId'], body={"doc": {"structAcronym": "Warning"}})
        else:
            print(f"le champ structAcronym existe dans {labo['_index']}")
            return labo['_source']['structAcronym']
