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


def esConnector(mode=mode):
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
