import os
from datetime import datetime

from sovisuhal.libs import esActions

path = "backup"
snapshot_name = f"snapshot_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
print(snapshot_name)
is_exist = os.path.exists(path)
print(is_exist)

if not is_exist:
    os.makedirs(path)

repository_settings = {"type": "fs", "settings": {"location": path, "compress": "true"}}

snapshot_settings = {
    "settings": {
        "indices": "*",
        "ignore_unavailable": "true",
        "include_global_state": "true",
    }
}

es = esActions.es_connector()

es.snapshot.create_repository(repository=path, body=repository_settings)
print("create repository done")

es.snapshot.create(
    repository=path,
    snapshot=snapshot_name,
    body=snapshot_settings,
    wait_for_completion=True,
    request_timeout=60,
)
print("Snapshot created")

print(
    "snapshot get:"
    + f" \n {es.snapshot.get(repository=path, snapshot='_all', filter_path='snapshots.snapshot')}"
)
