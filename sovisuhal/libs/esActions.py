from elasticsearch import Elasticsearch

try:
    from decouple import config
    from ldap3 import Server, Connection, ALL
    from uniauth.decorators import login_required

    mode = config("mode")  # Prod --> mode = 'Prod' en env Var

except:
    from django.contrib.auth.decorators import login_required

    mode = "Dev"
    structId = "198307662"  # UTLN


def es_connector(mode=mode):
    if mode == "Prod":

        secret = config('ELASTIC_PASSWORD')
        # context = create_ssl_context(cafile="../../stackELK/secrets/certs/ca/ca.crt")
        es = Elasticsearch('localhost',
                           http_auth=('elastic', secret),
                           scheme="http",
                           port=9200,
                           # ssl_context=context,
                           timeout=10)
    else:
        es = Elasticsearch([{'host': 'localhost', 'port': 9200}])
    return es


# Elastic match query call
def scope_all():
    scope = {
        "query": {
            "match_all": {}
        }
    }
    return scope


def scope_p(scope_field, scope_value):
    scope = {
        "query": {
            "match": {
                scope_field: scope_value
            }
        }
    }
    return scope


def date_all():
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


def date_p(scope_field, scope_value):
    start_date_param = {
        "size": 1,
        "sort": [
            {"submittedDate_tdate": {"order": "asc"}}
        ],
        "query": {
            "match_phrase": {scope_field: scope_value}
        }
    }
    return start_date_param


def ref_p(scope_bool_type, scope_field, scope_value, validate, date_range_type, scope_date_from, scope_date_to):
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


# ref_param = esActions.ref_p(scope_bool_type, ext_key, entity[key], validate, date_range_type, dateFrom, dateTo)


def ref_p_filter(filter, scope_bool_type, scope_field, scope_value, validate, date_range_type, scope_date_from,
                 scope_date_to):
    if filter == "uncomplete":
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

    elif filter == "complete":
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


# ref_param = esActions.ref_p_alt(filter, scope_bool_type, ext_key, entity[key], validate, date_range_type, dateFrom, dateTo)


def confirm_p(scope_field, scope_value, validate):
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