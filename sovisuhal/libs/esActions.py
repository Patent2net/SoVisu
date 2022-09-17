from elasticsearch import Elasticsearch

try:
    from decouple import config
    from ldap3 import Server, Connection, ALL
    from uniauth.decorators import login_required

    mode = config("mode")  # Prod --> mode = 'Prod' en env Var

except:
    from django.contrib.auth.decorators import login_required

    mode = "Dev"


# Use that base code in other files to use es_connector function: es = esActions.es_connector()
def es_connector(mode=mode):
    """
    Assure la connexion de SoVisu à l'instance ElasticSearch
    """
    if mode == "Prod":

        secret = config('ELASTIC_PASSWORD')
        # context = create_ssl_context(cafile="../../stackELK/secrets/certs/ca/ca.crt")
        es = Elasticsearch('localhost',
                           http_auth=('elastic', secret),
                           scheme="http",
                           port=9200)

    else:
        #es = Elasticsearch([{'host': 'localhost', 'port': 9200}])
        es = Elasticsearch('http://localhost:9200', http_compress=True,  connections_per_node=5, request_timeout=200, retry_on_timeout=True)

        es.options(request_timeout=100, retry_on_timeout= True, max_retries=5).cluster.health(
            wait_for_no_initializing_shards=True,
            wait_for_no_relocating_shards=False,
            wait_for_status="green" # yellow doit pas forcément marcher si pas un cluster !
        )

    return es


# Elastic match query call

# Use that base code in other files to use scope_all function: variable_name = esActions.scope_all()
def scope_all():
    """
    Paramètre pour les requêtes ElasticSearch, retourne tous les documents
    """
    scope = {
        "query": {
            "match_all": {}
        }
    }
    return scope


# Use that base code in other files to use scope_p function: variable_name = esActions.scope_p(scope_field, scope_value)
def scope_p(scope_field, scope_value):
    """
    Paramètre pour les requêtes ElasticSearch, retourne un ensemble de documents spécifique en fonction d'un filtre
    """
    scope = {
        "query": {
            "match": {
                scope_field: scope_value
            }
        }
    }
    return scope


# Use that base code in other files to use date_all function: variable_name = esActions.date_all()
def date_all():
    """
    Paramètre pour les requêtes ElasticSearch, retourne tous les documents, triés par date de publication
    """
    start_date_param = {
        "size": 1,
        "sort": [
            {"submittedDate_tdate": {"order": "asc"}}
        ],
        "query": {
            "match_all": {}
        }

    }
    return start_date_param


# Use that base code in other files to use date_p function: variable_name = esActions.date_p(scope_field, scope_value)
def date_p(scope_field, scope_value):
    """
    Paramètre pour les requêtes ElasticSearch, retourne un ensemble de documents spécifique en fonction d'un filtre, triés par date de publication
    """
    start_date_param = {
        "size": 1,
        "sort": [
            {"producedDate_tdate": {"order": "asc"}}
        ],
        "query": {
            "match_phrase": {scope_field: scope_value}
        }
    }
    return start_date_param


# Use that base code in other files to use ref_p function: variable_name = esActions.ref_p(scope_bool_type, ext_key,
# entity[key], validate, date_range_type, dateFrom, dateTo)

def ref_p(scope_bool_type, scope_field, scope_value, validate, date_range_type, scope_date_from, scope_date_to):
    """
    Paramètre pour les requêtes ElasticSearch, retourne un ensemble de documents spécifique en fonction de différents filtres, dans une période donnée
    """
    ref_param = {
        "query": {
            "bool": {
                scope_bool_type: [
                    {
                        "match_phrase": {
                            scope_field: scope_value
                        }
                    },
                    {
                        "match": {
                            "validated": validate
                        }
                    },
                    {
                        "range": {
                            date_range_type: {
                                "gte": scope_date_from,
                                "lt": scope_date_to
                            }
                        }
                    }
                ]
            }
        }
    }
    return ref_param


# Use that base code in other files to use ref_p_filter function: variable_name = esActions.ref_p_filter(filter,
# scope_bool_type, ext_key, entity[key], validate, date_range_type, dateFrom, dateTo)

def ref_p_filter(p_filter, scope_bool_type, scope_field, scope_value, validate, date_range_type, scope_date_from,
                 scope_date_to):
    """
    Paramètre pour les requêtes ElasticSearch, retourne un ensemble de documents spécifique en fonction de différents filtres, dans une période donnée et d'un filtre p_filter("uncomplete","complete", "all").
    """
    if p_filter == "uncomplete":
        ref_param = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "bool": {
                                "must": [
                                    {
                                        "match_phrase": {
                                            scope_field: scope_value,
                                        }
                                    },
                                    {
                                        "match": {
                                            "validated": validate,
                                        }
                                    },
                                    {
                                        "range": {
                                            "submittedDate_tdate": {
                                                "gte": scope_date_from,
                                                "lt": scope_date_to
                                            }
                                        }
                                    },
                                ]
                            }
                        },
                        {
                            "bool": {
                                "must_not": [
                                    {
                                        "exists": {
                                            "field": "fileMain_s"
                                        }
                                    },
                                    {
                                        "exists": {
                                            "field": "*_abstract_s"
                                        }
                                    }
                                ]
                            }
                        }
                    ]
                }
            }
        }

    elif p_filter == "complete":
        ref_param = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "bool": {
                                "must": [
                                    {
                                        "match_phrase": {
                                            scope_field: scope_value,
                                        }
                                    },
                                    {
                                        "match": {
                                            "validated": validate,
                                        }
                                    },
                                    {
                                        "range": {
                                            "submittedDate_tdate": {
                                                "gte": scope_date_from,
                                                "lt": scope_date_to
                                            }
                                        }
                                    },
                                ]
                            }
                        },
                        {
                            "bool": {
                                "must": [
                                    {
                                        "exists": {
                                            "field": "fileMain_s"
                                        }
                                    },
                                    {
                                        "exists": {
                                            "field": "*_abstract_s"
                                        }
                                    }
                                ]
                            }
                        }
                    ]
                }
            }
        }
    else:
        ref_param = ref_p(scope_bool_type, scope_field, scope_value, validate, date_range_type, scope_date_from,
                          scope_date_to)
    return ref_param


def confirm_p(scope_field, scope_value, validate):
    """
    Paramètre pour les requêtes ElasticSearch, retourne un ensemble de documents spécifique en fonction d'un filtre, qui ont leur champ validated à une certaine valeur.
    """
    has_to_confirm_param = {
        "query": {
            "bool": {
                "must": [
                    {
                        "match_phrase": {
                            scope_field: scope_value
                        }
                    },
                    {
                        "match": {
                            "validated": validate
                        }
                    }
                ]
            }
        }
    }
    return has_to_confirm_param
