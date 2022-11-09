from sovisuhal.libs import esActions

path = "backup1"
es = esActions.es_connector()
"""
print(f"snapshot get_repository: \n {es.snapshot.get_repository(repository=path, local=True)}")

snapshot_name = es.snapshot.get(repository=path, snapshot='_all', filter_path='snapshots.snapshot')
print(f"snapshot get: \n {snapshot_name}")

"""
# print(f"snapshot status: \n {es.snapshot.status(repository=path, snapshot='snapshot_2022-06-10_14-12-29')}")

# es.snapshot.delete(repository=path, snapshot='snapshot_2022-06-10_14-12-29')
name_test = 'snapshot_2022-06-22_18-19-18'  # use a snapshot name shown by snapshot.get()
#["*-researchers", "*-documents", "*-researchers-*", "*-documents-*"]
restore_index_body = {"indices": ["*"]}
print(f"closing all the indices. state: {es.indices.close(index='_all')}")  # necessary to restore
print(es.snapshot.restore(repository=path, snapshot=name_test, body=restore_index_body, request_timeout=60))

print(f"Opening all the indices. state: {es.indices.open(index='_all')}")  # indices can be not reopened, security to avoid kibana crash


"""
# use to delete all snapshots and cleanup the repository
if snapshot_name:
    cleaned_snap = [snap['snapshot'] for snap in snapshot_name['snapshots']]
    print(cleaned_snap)
    for snap in cleaned_snap:
        print(f"treating {snap} snapshot")
        es.snapshot.delete(repository=path, snapshot=snap)

es.snapshot.cleanup_repository(repository=path)

print(es.snapshot.delete_repository(repository=path))
"""