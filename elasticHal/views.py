# from django.shortcuts import render
from sovisuhal.libs import esActions

es = esActions.es_connector()


def get_index_list():
    indexes = ()
    scope_param = esActions.scope_all()
    count = es.count(index="*-laboratories", body=scope_param, request_timeout=50)['count']
    if count > 0:
        result = es.search(index="*-laboratories", body=scope_param, size=count)
        result = result['hits']['hits']
        print(result)
        indexes = []
        for lab in result:
            indexes.append((lab["_index"], lab["_source"]["acronym"]+' (' + lab["_source"]["structAcronym"] + ')'))
        indexes = tuple(indexes)
    return indexes
