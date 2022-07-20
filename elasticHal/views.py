# from django.shortcuts import render
from sovisuhal.libs import esActions
from elasticHal.libs import StructAcronym
es = esActions.es_connector()


def get_index_list():
    """
    Get list of laboratories indices from Elasticsearch
    :return: list of indices
    """
    indexes = ()
    scope_param = esActions.scope_all()
    count = es.count(index="*-laboratories", body=scope_param, request_timeout=50)['count']
    if count > 0:
        result = es.search(index="*-laboratories", body=scope_param, size=count)
        result = result['hits']['hits']
        print(result)
        indexes = []

        # si lab pas de structAcronym alors récupérer le struc Acronyme en fonction de l'index du laboratoire.
        for lab in result:
            if "structAcronym" in lab["_source"].keys():
                indexes.append((lab["_index"], lab["_source"]["acronym"] + ' (' + lab["_source"]["structAcronym"] + ')'))

            else:
                structAcronym = StructAcronym.return_struct_from_index(lab["_index"])
                indexes.append((lab["_index"], lab["_source"]["acronym"] + ' (' + structAcronym + ')'))

        indexes = tuple(indexes)
    return indexes
