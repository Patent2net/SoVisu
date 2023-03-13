# from libs import hal, utils, unpaywall, scanR
import datetime
import json

from celery import shared_task
from celery_progress.backend import ProgressRecorder
from decouple import config
from django.shortcuts import redirect
from elasticsearch import helpers
from ldap3 import ALL, Connection, Server

from elasticHal.libs import (
    doi_enrichissement,
    hal,
    keyword_enrichissement,
    location_docs,
    utils,
)
from elasticHal.libs.archivesOuvertes import get_aurehalId, get_concepts_and_keywords

from . import esActions

# from uniauth.decorators import login_required


mode = config("mode")  # Prod --> mode = 'Prod' en env Var

"""
try:
    from decouple import config
    from ldap3 import ALL, Connection, Server
    from uniauth.decorators import login_required

    mode = config("mode")  # Prod --> mode = 'Prod' en env Var

except:
    from django.contrib.auth.decorators import login_required

    mode = "Dev"
    structId = "198307662"  # UTLN
"""

# Connect to DB
es = esActions.es_connector()


# @shared_task(bind=True)
def indexe_chercheur(ldapid, labo_accro, labhalid, idhal, idref, orcid):  # self,
    """
    Indexe un chercheur dans Elasticsearch
    """
    #   progress_recorder = ProgressRecorder(self)
    #   progress_recorder.set_progress(0, 10, description='récupération des données LDAP')
    if mode == "Prod":
        server = Server("ldap.univ-tln.fr", get_info=ALL)
        conn = Connection(
            server,
            "cn=Sovisu,ou=sysaccount,dc=ldap-univ-tln,dc=fr",
            config("ldappass"),
            auto_bind=True,
        )  # recup des données ldap
        conn.search(
            "dc=ldap-univ-tln,dc=fr",
            "(&(uid=" + ldapid + "))",
            attributes=[
                "displayName",
                "mail",
                "typeEmploi",
                "ustvstatus",
                "supannaffectation",
                "supanncodeentite",
                "supannEntiteAffectationPrincipale",
                "labo",
            ],
        )
        dico = json.loads(conn.response_to_json())["entries"][0]
        structid = config("structId")
    else:
        dico = {
            "attributes": {
                "displayName": "REYMOND David",
                "labo": [],
                "mail": ["david.reymond@univ-tln.fr"],
                "supannAffectation": ["IMSIC", "IUT TC"],
                "supannEntiteAffectationPrincipale": "IUTTCO",
                "supanncodeentite": [],
                "typeEmploi": "Enseignant Chercheur Titulaire",
                "ustvStatus": ["OFFI"],
            },
            "dn": "uid=dreymond,ou=Personnel,ou=people,dc=ldap-univ-tln,dc=fr",
        }
        structid = "198307662"
        ldapid = "dreymond"
    labo = labhalid

    extrait = dico["dn"].split("uid=")[1].split(",")
    chercheur_type = extrait[1].replace("ou=", "")
    suppan_id = extrait[0]
    if suppan_id != ldapid:
        print("aille", ldapid, " --> ", ldapid)
    nom = dico["attributes"]["displayName"]
    emploi = dico["attributes"]["typeEmploi"]
    mail = dico["attributes"]["mail"]
    if "supannAffectation" in dico["attributes"].keys():
        supann_affect = dico["attributes"]["supannAffectation"]
    else:
        supann_affect = []

    if "supannEntiteAffectationPrincipale" in dico["attributes"].keys():
        supann_princ = dico["attributes"]["supannEntiteAffectationPrincipale"]
    else:
        supann_princ = []

    if not len(nom) > 0:
        nom = [""]
    elif not len(emploi) > 0:
        emploi = [""]
    elif not len(mail) > 0:
        mail = [""]

    # name,type,function,mail,lab,supannAffectation,supannEntiteAffectationPrincipale,halId_s,labHalId,idRef,structDomain,firstName,lastName,aurehalId
    chercheur = dict()
    # as-t-on besoin des 3 derniers champs ???
    chercheur["name"] = nom
    chercheur["type"] = chercheur_type
    chercheur["function"] = emploi
    chercheur["mail"] = mail[0]
    chercheur["orcId"] = orcid
    chercheur["lab"] = labo_accro  # acronyme
    chercheur["supannAffectation"] = ";".join(supann_affect)
    chercheur["supannEntiteAffectationPrincipale"] = supann_princ
    chercheur["firstName"] = chercheur["name"].split(" ")[1]
    chercheur["lastName"] = chercheur["name"].split(" ")[0]

    # Chercheur["aurehalId"]

    # creation des index
    #  progress_recorder.set_progress(5, 10, description='creation des index')
    if not es.indices.exists(index=structid + "-structures"):
        es.indices.create(index=structid + "-structures")
    if not es.indices.exists(index=structid + "-" + labo + "-researchers"):
        es.indices.create(index=structid + "-" + labo + "-researchers")
        es.indices.create(
            index=structid + "-" + labo + "-researchers-" + ldapid + "-documents"
        )  # -researchers" + row["ldapId"] + "-documents
    else:
        if not es.indices.exists(
            index=structid + "-" + labo + "-researchers-" + ldapid + "-documents"
        ):
            es.indices.create(
                index=structid + "-" + labo + "-researchers-" + ldapid + "-documents"
            )  # -researchers" + row["ldapId"] + "-documents" ?

    chercheur["structSirene"] = structid
    chercheur["labHalId"] = labo
    chercheur["validated"] = False
    chercheur["ldapId"] = ldapid
    chercheur["Created"] = datetime.datetime.now().isoformat()

    # New step ?

    if idhal != "":
        aurehal = get_aurehalId(idhal)
        # integration contenus
        archives_ouvertes_data = get_concepts_and_keywords(aurehal)
    else:  # sécurité, le code n'est pas censé être lancé par create car vérification du champ idhal
        return redirect("unknown")
        # retourne sur check() ?

    chercheur["halId_s"] = idhal
    chercheur["validated"] = False
    chercheur["aurehalId"] = aurehal  # heu ?
    chercheur["concepts"] = archives_ouvertes_data["concepts"]
    chercheur["guidingKeywords"] = []
    chercheur["idRef"] = idref
    chercheur["axis"] = labo_accro

    # Chercheur["mappings"]: {
    #     "_default_": {
    #         "_timestamp": {
    #             "enabled": "true",
    #             "store": "true",
    #             "path": "plugins.time_stamp.string",
    #             "format": "yyyy-MM-dd HH:m:ss"
    #         }
    #     }}
    res = es.index(
        index=chercheur["structSirene"] + "-" + chercheur["labHalId"] + "-researchers",
        id=chercheur["ldapId"],
        body=json.dumps(chercheur),
        refresh="wait_for",
    )
    print("statut de la création d'index: ", res["result"])
    return chercheur


@shared_task(bind=True)
def collecte_docs(self, chercheur, overwrite=False):  # self,
    """
    Collecte les documents d'un chercheur
    """
    init = overwrite  # If True, data persistence is lost when references are updated
    docs = hal.find_publications(chercheur["halId_s"], "authIdHal_s")

    progress_recorder = ProgressRecorder(self)
    progress_recorder.set_progress(0, len(docs), description="récupération des données HAL")
    # Insert documents collection
    for num, doc in enumerate(docs):
        doc["country_colaboration"] = location_docs.generate_countrys_fields(doc)
        doc = doi_enrichissement.docs_enrichissement_doi(doc)
        if "fr_abstract_s" in doc.keys():
            if isinstance(doc["fr_abstract_s"], list):
                doc["fr_abstract_s"] = "/n".join(doc["fr_abstract_s"])
            if len(doc["fr_abstract_s"]) > 100:
                doc["fr_entites"] = keyword_enrichissement.return_entities(
                    doc["fr_abstract_s"], "fr"
                )
                doc["fr_teeft_keywords"] = keyword_enrichissement.keyword_from_teeft(
                    doc["fr_abstract_s"], "fr"
                )
        if "en_abstract_s" in doc.keys():
            if isinstance(doc["en_abstract_s"], list):
                doc["en_abstract_s"] = "/n".join(doc["en_abstract_s"])
            if len(doc["en_abstract_s"]) > 100:
                doc["en_entites"] = keyword_enrichissement.return_entities(
                    doc["en_abstract_s"], "en"
                )
                doc["en_teeft_keywords"] = keyword_enrichissement.keyword_from_teeft(
                    doc["en_abstract_s"], "en"
                )

        doc["_id"] = doc["docid"]
        doc["validated"] = True

        doc["harvested_from"] = "researcher"

        doc["harvested_from_ids"] = []
        doc["harvested_from_label"] = []


        #
        #
        # print(doc["authorship"], doc ['authLastName_s'])

        # en espérant que doc["authIdHal_s"] présente la liste des idhal auteur avec "" si pas d'idhal (et donc
        if len(doc["authIdHal_s"]) != len(doc["authLastName_s"]):
            #print ("elastichal.py : test d'autorat no good")
            # test sur le nom complet...
            nom = [truc for truc in doc["authLastName_s"] if chercheur["lastName"].lower() in truc.lower()]  # pour les récemment mariés qui auraient un nom composé... Après si 'lun des co-auteur porte le même nom...
            if len(nom)>0:
                nom = nom[0] .title()
                try:
                    if doc["authLastName_s"].index(nom) == 0: # premier
                        doc["authorship"] = [
                            {"authorship": "firstAuthor", "authIdHal_s": chercheur["halId_s"]}
                        ]  # pas voulu casser le modele de données ici mais first, last ou rien suffirait non ?
                    elif (
                        doc["authLastName_s"].index(nom)
                        == len(doc["authLastName_s"]) - 1
                    ):  # dernier
                        doc["authorship"] = [{"authorship": "lastAuthor", "authIdHal_s": chercheur["halId_s"]}]
                except:
                    doc["authorship"] = []
            else:
                doc["authorship"] = []
        elif chercheur["halId_s"] in doc["authIdHal_s"]:
            if doc["authIdHal_s"].index(chercheur["halId_s"])==0:
                doc["authorship"] = [
                                 {"authorship": "firstAuthor", "authIdHal_s": chercheur["halId_s"]}
                            ]
            elif (doc["authIdHal_s"].index(chercheur["halId_s"]) == len(doc["authIdHal_s"]) - 1):  # dernier
                doc["authorship"] = [{"authorship": "lastAuthor", "authIdHal_s": chercheur["halId_s"]}]
            else:
                doc["authorship"] = []
        else:
            doc["authorship"] = []

        doc["harvested_from_ids"].append(chercheur["halId_s"])

        # historique d'appartenance du docId
        # pour attribuer les bons docs aux chercheurs
        # harvet_history.append({'docid': doc['docid'], 'from': row['halId_s']})
        #
        # for h in harvet_history:
        #     if h['docid'] == doc['docid']:
        #         if h['from'] not in doc["harvested_from_ids"]:
        #             doc["harvested_from_ids"].append(h['from'])

        doc["records"] = []

        doc["MDS"] = utils.calculate_mds(doc)

        try:
            should_be_open = utils.should_be_open(doc)
            if should_be_open == 1:
                doc["should_be_open"] = True
            if should_be_open == -1:
                doc["should_be_open"] = False

            if should_be_open == 1 or should_be_open == 2:
                doc["isOaExtra"] = True
            elif should_be_open == -1:
                doc["isOaExtra"] = False
        except IndexError:
            print("publicationDate_tdate error ?")
        doc["Created"] = datetime.datetime.now().isoformat()

        if not init: # récupération de l'existant pour ne pas écraser
            field = "_id"
            doc_param = esActions.scope_p(field, doc["_id"])

            if not es.indices.exists(
                index=chercheur["structSirene"]
                + "-"
                + chercheur["labHalId"]
                + "-researchers-"
                + chercheur["ldapId"]
                + "-documents"
            ):  # -researchers" + row["ldapId"] + "-documents
                print("exception ", chercheur["labHalId"], chercheur["ldapId"])

            res = es.search(
                index=chercheur["structSirene"]
                + "-"
                + chercheur["labHalId"]
                + "-researchers-"
                + chercheur["ldapId"]
                + "-documents",
                body=doc_param,
            )  # -researchers" + row["ldapId"] + "-documents

            if len(res["hits"]["hits"]) > 0:
                doc["validated"] = res["hits"]["hits"][0]["_source"]["validated"]
                if "authorship" in res["hits"]["hits"][0]["_source"]:
                    doc["authorship"] = res["hits"]["hits"][0]["_source"]["authorship"]

                if (
                    res["hits"]["hits"][0]["_source"]["modifiedDate_tdate"]
                    != doc["modifiedDate_tdate"]
                ):
                    doc["records"].append(
                        {
                            "beforeModifiedDate_tdate": doc["modifiedDate_tdate"],
                            "MDS": res["hits"]["hits"][0]["_source"]["MDS"],
                        }
                    )

            else:
                doc["validated"] = True
        progress_recorder.set_progress(num, len(docs), description="(récolte)")
    progress_recorder.set_progress(num, len(docs), description="(indexation)")
    helpers.bulk(
        es,
        docs,
        index=chercheur["structSirene"]
        + "-"
        + chercheur["labHalId"]
        + "-researchers-"
        + chercheur["ldapId"]
        + "-documents"
        # -researchers" + row["ldapId"] + "-documents
    )

    return chercheur  # au cas où
