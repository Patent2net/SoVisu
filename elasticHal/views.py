# from django.shortcuts import render
from sovisuhal.libs import esActions
es = esActions.es_connector()
# Create your views here.
# Set choices to an empty list as it is a required argument.


def get_index_list():
    scope_param = esActions.scope_all()
    count = es.count(index="*-laboratories", body=scope_param, request_timeout=50)['count']
    result = es.search(index="*-laboratories", body=scope_param, size=count,
                       filter_path=["hits.hits._index, hits.hits._source.acronym"])
    result = result['hits']['hits']
    #print(f"result = {result}")
    indexes = []
    for lab in result:
        indexes.append((lab["_index"], lab["_source"]["acronym"]))
    indexes = tuple(indexes)
    #print(f"indexes2 content {indexes}")
    return indexes
