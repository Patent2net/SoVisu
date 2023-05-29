from decouple import config
from elasticsearch import Elasticsearch

# from ldap3 import ALL, Connection, Server
# from uniauth.decorators import login_required

mode = config("mode")  # Prod --> mode = 'Prod' en env Var


# To call es_connector function: es = esActions.es_connector()
def es_connector(mode=mode):
    """
    Assure la connexion de SoVisu à l'instance ElasticSearch
    """
    if mode == "Prod":
        secret = config("ELASTIC_PASSWORD_SOVISU")
        # context = create_ssl_context(cafile="../../stackELK/secrets/certs/ca/ca.crt")
        es = Elasticsearch(
            "http://elasticsearch:9200",
            basic_auth=("sovisu", secret),
            http_compress=True,
            connections_per_node=5,
            request_timeout=200,
            retry_on_timeout=True,
        )
        es.options(request_timeout=100, retry_on_timeout=True, max_retries=5)

    else:
        # es = Elasticsearch([{'host': 'localhost', 'port': 9200}])
        es = Elasticsearch(
            "http://localhost:9200",
            http_compress=True,
            connections_per_node=5,
            request_timeout=200,
            retry_on_timeout=True,
        )

        es.options(request_timeout=100, retry_on_timeout=True, max_retries=5).cluster.health(
            wait_for_no_initializing_shards=True,
            wait_for_no_relocating_shards=False,
            wait_for_status="yellow",  # green  doit pas forcément marcher si pas un cluster !
        )

    return es


# Elastic match query call


# To call scope_all function: variable_name = esActions.scope_all()
def scope_all():
    """
    Paramètre pour les requêtes ElasticSearch, retourne tous les documents
    """
    scope = {"match_all": {}}
    return scope


# To call scope_p function: variable_name = esActions.scope_p(scope_field, scope_value)
def scope_p(scope_field, scope_value):
    """
    Retourne un ensemble de documents spécifique en fonction d'un filtre
    """
    scope = {"match": {scope_field: scope_value}}
    return scope

def scope_term(scope_field, scope_value):
    """
    Retourne un ensemble de documents spécifiques en fonction d'un filtre
    sur matching EXACT
    """
    scope = {"term": {scope_field: scope_value}}
    return scope

def scope_term_multi(list_scope_field_value):
    """
    Retourne un ensemble de documents spécifiques en fonction d'un filtre
    sur matchings MAIS alors que les autres fonctionne sur les notices celui là non !!!
    du coup passé à match.
    Pour mémo le match_phrase_prefix devrait être utile pour parcourir les arbres des domaines disciplinaires
    """
    temp = []
    for match in list_scope_field_value:
        temp .append(scope_term(match[0], match[1]))
    return {'bool': {'should': temp}}

def scope_match(scope_field, scope_value):
    """
    Retourne un ensemble de documents spécifiques en fonction d'un filtre
    sur matching EXACT
    """
    scope = {"match": {scope_field: scope_value}}
    return scope

def scope_match_multi(list_scope_field_value):
    """
    Retourne un ensemble de documents spécifiques en fonction d'un filtre
    sur matchings EXACT
    """
    temp = []
    for match in list_scope_field_value:
        temp .append(scope_match(match[0], match[1]))
    return {'bool': {'must': temp}}
# To call date_all function: variable_name = esActions.date_all()
def date_all():
    """
    Retourne tous les documents, triés par date de publication
    """
    start_date_param = {
        "size": 1,
        "sort": [
            {"producedDate_tdate": {"order": "asc"}}
        ],  # champ de date de production. Non Vide sur HAL.
        "query": {"match_all": {}},
    }
    return start_date_param


# To call date_p function: variable_name = esActions.date_p(scope_field, scope_value)
def date_p(scope_field, scope_value):
    """
    Retourne un ensemble de documents spécifique en fonction d'un filtre,
    triés par date de publication
    """
    start_date_param = {
        "size": 1,
        "sort": [{"producedDate_tdate": {"order": "asc"}}],
        "query": {"match_phrase": {scope_field: scope_value}},
    }
    return start_date_param


# To call ref_p function: variable_name = esActions.ref_p(scope_bool_type, ext_key,
# entity[key], validate, date_range_type, dateFrom, dateTo)
def ref_p(
    scope_bool_type,
    scope_field,
    scope_value,
    validate,
    date_range_type,
    scope_date_from,
    scope_date_to,
):
    """
    Retourne un ensemble de documents spécifique en fonction de différents filtres,
    dans une période donnée
    """
    ref_param = {
        "bool": {
            scope_bool_type: [
                {"match_phrase": {scope_field: scope_value}},
                {"match": {"validated": validate}},
                {
                    "range": {
                        date_range_type: {
                            "gte": scope_date_from,
                            "lt": scope_date_to,
                        }
                    }
                },
            ]
        }
    }
    return ref_param


# To call ref_p_filter function: variable_name = esActions.ref_p_filter(filter,
# scope_bool_type, ext_key, entity[key], validate, date_range_type, dateFrom, dateTo)


def ref_p_filter(
    p_filter,
    scope_bool_type,
    scope_field,
    scope_value,
    validate,
    date_range_type,
    scope_date_from,
    scope_date_to,
):
    """
    Retourne un ensemble de documents spécifique en fonction de différents filtres,
    dans une période donnée et d'un filtre p_filter("uncomplete","complete", "all").
    """
    if p_filter == "uncomplete":
        ref_param = {
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
                                        "producedDate_tdate": {
                                            "gte": scope_date_from,
                                            "lt": scope_date_to,
                                        }
                                    }
                                },
                            ]
                        }
                    },
                    {
                        "bool": {
                            "must": [
                                {"range": {"MDS": {"lt": 70}}},
                            ]
                        }
                    },
                ]
            }
        }

    elif p_filter == "complete":
        ref_param = {
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
                                        "producedDate_tdate": {
                                            "gte": scope_date_from,
                                            "lt": scope_date_to,
                                        }
                                    }
                                },
                            ]
                        }
                    },
                    {
                        "bool": {
                            "must": [
                                {"range": {"MDS": {"gte": 100}}},
                            ]
                        }
                    },
                ]
            }
        }
    else:
        ref_param = ref_p(
            scope_bool_type,
            scope_field,
            scope_value,
            validate,
            date_range_type,
            scope_date_from,
            scope_date_to,
        )
    return ref_param


def confirm_p(scope_field, scope_value, validate):
    """
    Retourne un ensemble de documents spécifique en fonction d'un filtre,
    qui ont leur champ validated à une certaine valeur.
    """
    has_to_confirm_param = {
        "bool": {
            "must": [
                {"match_phrase": {scope_field: scope_value}},
                {"match": {"validated": validate}},
            ]
        }
    }
    return has_to_confirm_param


def validated_searcherprofile_p(p_id, validate, date_range_type, date_from, date_to):
    validated_searcherprofile = {
            "bool": {
                "must": [
                     {
                         "nested": {
                             "path": "SearcherProfile",
                             "query": {
                                 "bool": {
                                     "must": [
                                         {"term": {"SearcherProfile.ldapId.keyword": p_id}},
                                         {"term": {"SearcherProfile.validated": validate}}
                                     ]
                                 }
                             },
                             "inner_hits": {}  # Include only the matched nested documents
                         }
                     },
                    {
                        "range": {
                            date_range_type: {
                                "gte": date_from,
                                "lt": date_to
                            }
                        }
                    }
                ]
            }
        }
    return validated_searcherprofile
