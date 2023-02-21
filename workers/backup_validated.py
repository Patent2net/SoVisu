import json

from sovisuhal.libs import esActions

es = esActions.es_connector()

q = {"query": {"match": {"validated": True}}}
count = es.count(index="*-documents", body=q)["count"]
docs = es.search(index="*-documents", body=q, size=count)
r_count = docs["hits"]["total"]["value"]

print("found " + str(r_count) + "/" + str(count) + " docs")

dump = []

for doc in docs["hits"]["hits"][0:5]:
    dump.append({"docid": doc["_id"], "index": doc["_index"]})


with open("data/dump.json", "w") as outfile:
    json.dump(dump, outfile)
