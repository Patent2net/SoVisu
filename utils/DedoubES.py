from datetime import datetime

from constants import TIMEZONE
from sovisuhal.libs import esActions

# Connect to DB
es = esActions.es_connector()

# Memo des pbs.
# Choix fait de se poser sur le ldapid --> pas de gestion des doublons type ex-doctorants
# si deux meme ldapid dans des index chercheurs différents alors
# memo du plus recent created seulement
scope_param = esActions.scope_all()
count = es.count(index="*-researchers", body=scope_param)["count"]
res = es.search(index="*-researchers", body=scope_param, size=count)
chercheurs = res["hits"]["hits"]

ldapList = [cher["_source"]["ldapId"] for cher in chercheurs]
doublons = [cher for cher in chercheurs if ldapList.count(cher["_source"]["ldapId"]) > 1]
cpt = 0
Vus, lstRetenus = [], []
for ind, doudou in enumerate(doublons):
    if "Created" in doudou["_source"].keys():
        dateCrea = doudou["_source"]["Created"]
        if doudou["_source"]["ldapId"] not in Vus:
            Vus.append(doudou["_source"]["ldapId"])
            retenu = doudou
            if ind < len(doublons) - 1:
                Autres = [
                    doub
                    for doub in doublons[ind + 1:]
                    if doub["_source"]["ldapId"] == doudou["_source"]["ldapId"]
                ]
                for dub in Autres:
                    if dub["_source"]["Created"] > dateCrea:
                        retenu = dub
            lstRetenus.append(retenu)

        else:
            pass
    else:
        # pas venu depuis changement de mode avec Created
        Autres = [
            doub
            for doub in doublons[ind + 1:]
            if doub["_source"]["ldapId"] == doudou["_source"]["ldapId"]
        ]
        if len(Autres) == 0:
            doudou["_source"]["Created"] = datetime.now(tz=TIMEZONE).isoformat()
            lstRetenus.append(doudou)
print(
    len(lstRetenus),
    " sur ",
    len(doublons),
    " et ",
    len(set(ldapList)),
    " ldapId uniques ",
)
deDoub = [cher["_source"]["ldapId"] for cher in lstRetenus]

for cher in doublons:
    if cher not in lstRetenus:
        print("à supprimer ", cher["_index"], cher["_id"])
        es.delete(index=cher["_index"], id=cher["_id"])
        print(
            "supression de son index documents",
            cher["_index"] + "-" + cher["_id"] + "-documents",
        )
        try:
            es.indices.delete(index=cher["_index"] + "-" + cher["_id"] + "-documents")
        except IndexError:
            print("ok, pas besoin")

        # es.indices.delete(index=cher ['_source'])
        # es.indices.delete(index=cher['_source'] + "-documents")
