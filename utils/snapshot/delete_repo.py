from sovisuhal.libs import esActions

path = "backup"
es = esActions.es_connector()
print(es.snapshot.delete_repository(repository=path))
