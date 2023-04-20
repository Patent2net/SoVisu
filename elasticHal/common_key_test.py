from sovisuhal.libs import esActions

es = esActions.es_connector()

if __name__ == "__main__":
    publication = es.search(index="test_publications", size=1)
    publication = publication["hits"]["hits"][0]["_source"]
    print(publication)

    print("-------")
    searcher = es.search(index="test_researchers", size=1)
    searcher = searcher["hits"]["hits"][0]["_source"]
    print(searcher)

for key in publication:
    name = searcher.get(key, None)
    if name:
        print(key, end=" | ")
