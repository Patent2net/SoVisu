from sovisuhal.libs import esActions
import json


es = esActions.es_connector()

with open('data/dump.json') as json_file:
    data = json.load(json_file)


for doc in data:
    es.update(index=doc["index"], refresh='wait_for', id=doc["docid"], body={"doc": {"validated": True}})
