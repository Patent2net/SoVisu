from elasticsearch import Elasticsearch
from decouple import config


Mode = config("mode")

struct = "198307662"


def es_connector(mode=Mode):
    if mode == "Prod":
        secret = config("ELASTIC_PASSWORD")
        # context = create_ssl_context(cafile="../../stackELK/secrets/certs/ca/ca.crt")

        # es = Elasticsearch('localhost',
        #                    http_auth=('elastic', secret),
        #                    scheme="http",
        #                    port=9200,
        #                    # ssl_context=context,
        #                    timeout=10)
        es = Elasticsearch(
            "http://localhost:9200",
            basic_auth=("elastic", secret),
            http_compress=True,
            connections_per_node=5,
            request_timeout=200,
            retry_on_timeout=True,
        )
    else:
        print("Niet !!!")
        es = Elasticsearch([{"host": "localhost", "port": 9200}])

    return es


es = es_connector()

scope_param = {"query": {"match_all": {}}}
count = es.count(index=struct + "*-researchers", body=scope_param)["count"]
scope_param = {"query": {"match": {"labHalId": id}}}


res = es.search(index=struct + "*-researchers", body=scope_param, size=count)
entities = res["hits"]["hits"]

res = es.search(
    request_timeout=50,
    index=searcher["structSirene"]
    + "-"
    + searcher["labHalId"]
    + "-researchers-"
    + searcher["ldapId"]
    + "-documents",
    # -researchers" + searcher["ldapId"] + "-documents
)

query_param = {"match_all": {}}

count = es.count(index=struct + "*-researchers", query=query_param)["count"]
query_param = {"match": {"labHalId": "108098"}}

print(count)
res = es.search(index=struct + "*-researchers", query=query_param, size=count)
entities = res["hits"]["hits"]

print(Mode)

print(entities)
