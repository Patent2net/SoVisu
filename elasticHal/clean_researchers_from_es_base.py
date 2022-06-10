from elasticsearch import Elasticsearch
from datetime import datetime
import time


#############################################################################################
# Ce script permet de suprimer les doublons de chercheurs. Le scirpt récupére dans un premier
# Temps l'ensemble des chercheur , pour chaque chercheur il vérifie si il existe en double  au
# travers de sont halId. Une fois les doublons réperer , les index *-researchers et -*documents
# sont suprimer
#############################################################################################

print(time.strftime("%H:%M:%S", time.localtime()), end=' : ')
print("process start")

es = Elasticsearch([{'host': 'localhost', 'port': 9200}])  # Creation d'un instance ElasticSeach
structId = "198307662"  # UTLN Struct ID de l'universiter de Toulon

scope_param = {
        "query": {
            "match_all": {}
        }
    }
count = es.count(index="*-researchers", body=scope_param)['count']   # je crois que ça récuppere le nombre de laboratoire
res = es.search(index="*-researchers", body=scope_param, size=count)  # je crois que ça lance la requete avec la taille attendus


researchers = res['hits']['hits'] # pour chaque laboratoire
texting_dict = dict()


for index , researcher in enumerate(researchers):
    # créer un dictionaire permettant de stocker les chercheurs en fonction de leurs indexes
    if not researcher["_source"]["halId_s"] in texting_dict.keys():
        texting_dict.update({researcher["_source"]["halId_s"]: list()})
    texting_dict[researcher["_source"]["halId_s"]].append(index)

count_deleted = 0
for key in texting_dict:
    # on parcours le dictionaire précedament créer pour vérifier si un chercheur est enregistrer plusieurs fois
    if len(texting_dict[key]) > 1:
        # si le chercheur est enregistrer plusieurs fois
        list_of_date = list()

        for index in texting_dict[key]:
            # pour chaque enregistrement stock sous forme de liste la date de création du profil aisin que sont index
            list_of_date.append([datetime.strptime(researchers[index]["_source"]["Created"], "%Y-%m-%dT%H:%M:%S.%f"), index])

        while len(list_of_date) != 1:
            # tant qu'il ne reste pas 1 seul date dans list_of_date suprime les plus vieux compte
            index = researchers[min(list_of_date)[1]]["_index"]
            id = researchers[min(list_of_date)[1]]["_id"]
            query = {
                "query": {
                    "match_phrase": {
                        "_id": "" + researchers[min(list_of_date)[1]]["_id"] + ""
                    }
                }
            }
            es.delete_by_query(index=researchers[min(list_of_date)[1]]["_index"], body=query) #supressions du chercheur
            es.indices.delete(index= index + "-" + id + "-documents") #supressions des documents associer
            count_deleted = count_deleted+1
            list_of_date.remove(min(list_of_date))

print(str(count_deleted)+" doublons suprimés")
print(time.strftime("%H:%M:%S", time.localtime()), end=' : ')
print("process start")
