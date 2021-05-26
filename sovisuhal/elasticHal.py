#from libs import hal, utils, unpaywall, scanR

from sovisuhal.archivesOuvertes import getConceptsAndKeywords
from sovisuhal.libsElastichal import getAureHal
from sovisuhal.libs.unpaywall import getOa
from sovisuhal.libs import utils, hal, unpaywall
from elasticsearch import Elasticsearch, helpers
import json

try:
    from decouple import config
    from ldap3 import Server, Connection, ALL
    from uniauth.decorators import login_required
    mode = config("mode")  # Prod --> mode = 'Prod' en env Var
    structId = config("structId")
except:
    from django.contrib.auth.decorators import login_required
    mode = "Dev"
    structId = "198307662"# UTLN

from celery import shared_task
from celery_progress.backend import ProgressRecorder


#struct = "198307662"

def esConnector(mode = mode):
    if mode == "Prod":

        secret = config ('ELASTIC_PASSWORD')
        # context = create_ssl_context(cafile="../../stackELK/secrets/certs/ca/ca.crt")
        es = Elasticsearch('localhost',
                           http_auth=('elastic', secret),
                           scheme="http",
                           port=9200,
                           # ssl_context=context,
                           timeout=10)
    else:
        es = Elasticsearch([{'host': 'localhost', 'port': 9200}])
    return es




@shared_task(bind=True)
def indexe_chercheur (self, ldapId, tempoLab, idhal, idRef):
    es = esConnector()
    progress_recorder = ProgressRecorder(self)
    progress_recorder.set_progress(0, 10, description='récupération des données LDAP')
    if mode =="Prod":
        server = Server('ldap.univ-tln.fr', get_info=ALL)
        conn = Connection (server, 'cn=Sovisu,ou=sysaccount,dc=ldap-univ-tln,dc=fr', config ('ldappass'), auto_bind=True)# recup des données ldap
        conn.search('dc=ldap-univ-tln,dc=fr', '(&(uid='+ ldapId +'))', attributes = ['displayName', 'mail', 'typeEmploi', 'ustvstatus', 'supannaffectation', 'supanncodeentite','supannEntiteAffectationPrincipale',  'labo'])
        dico = json.loads(conn .response_to_json()) ['entries'] [0]

    else:
        dico = {'attributes': {'displayName': 'REYMOND David', 'labo': [], 'mail': ['david.reymond@univ-tln.fr'],
                               'supannAffectation': ['IMSIC', 'IUT TC'], 'supannEntiteAffectationPrincipale': 'IUTTCO',
                               'supanncodeentite': [], 'typeEmploi': 'Enseignant Chercheur Titulaire', 'ustvStatus': ['OFFI']},
                                'dn': 'uid=dreymond,ou=Personnel,ou=people,dc=ldap-univ-tln,dc=fr'}
        structId = "198307662"
        ldapId = 'dreymond'
    labo = tempoLab [0]
    connaitLab = labo # premier labo (au cas où) ???

    extrait = dico['dn'].split('uid=')[1].split(',')
    typeGus = extrait[1].replace('ou=', '')
    suppanId = extrait[0]
    if suppanId != ldapId:
        print ("aille", ldapId, ' --> ', ldapId)
    nom = dico['attributes']['displayName']
    Emploi = dico['attributes']['typeEmploi']
    mail = dico['attributes']['mail']
    if 'supannAffectation' in dico['attributes'].keys():
        supannAffect = dico['attributes']['supannAffectation']
    if 'supannEntiteAffectationPrincipale' in dico['attributes'].keys():
        supannPrinc = dico['attributes']['supannEntiteAffectationPrincipale']
    else:
        supannPrinc = []
    if not len(nom)>0:
        nom = ['']
    elif not len(Emploi) >0:
        Emploi = ['']
    elif not len (mail)  >0:
        mail = ['']

    # name,type,function,mail,lab,supannAffectation,supannEntiteAffectationPrincipale,halId_s,labHalId,idRef,structDomain,firstName,lastName,aurehalId
    Chercheur = dict()
    # as-t-on besoin des 3 derniers champs ???
    Chercheur ["name"] = nom
    Chercheur["type"] = typeGus
    Chercheur["function"] = Emploi
    Chercheur["mail"] = mail[0]

    Chercheur["lab"] = tempoLab [1]. strip() # acronyme
    Chercheur["supannAffectation"] = ";".join(supannAffect)
    Chercheur["supannEntiteAffectationPrincipale"] = supannPrinc
    Chercheur["firstName"] = Chercheur['name'].split(' ')[1]
    Chercheur["lastName"] = Chercheur['name'].split(' ')[0]
    # Chercheur["aurehalId"]

    # creation des index
    progress_recorder.set_progress(5, 10, description='creation des index')
    if not es.indices.exists(index=structId + "-structures"):
        es.indices.create(index=structId + "-structures")
    if not es.indices.exists(index=structId + "-" + labo  + "-researchers"):
        es.indices.create(index=structId + "-" + labo + "-researchers")
        es.indices.create(index=structId + "-" + labo + "-researchers-" + ldapId + "-documents")  # -researchers" + row["ldapId"] + "-documents
    else:
        if not es.indices.exists(index=structId + "-" + labo + "-researchers-" + ldapId + "-documents"):
            es.indices.create(index=structId + "-" + labo + "-researchers-" + ldapId + "-documents")  # -researchers" + row["ldapId"] + "-documents" ?


    Chercheur ["structSirene"] = structId
    Chercheur["labHalId"] = labo
    Chercheur["validated"] = False
    Chercheur["ldapId"] = ldapId

    #New step ?

    if idhal != '':
        aureHal = getAureHal(idhal)
        # integration contenus
        archivesOuvertesData = getConceptsAndKeywords(idhal)
    else:
        pass
        #retourne sur check() ?
    Chercheur["halId_s"] = idhal
    Chercheur["validated"] = False
    Chercheur["aurehalId"] = aureHal  # heu ?
    Chercheur["concepts"] = archivesOuvertesData['concepts']
    Chercheur["guidingKeywords"] = []
    Chercheur["idRef"] = idRef

    res = es.index(index=Chercheur["structSirene"] + "-" + Chercheur["labHalId"] + "-researchers",
                   id=Chercheur["ldapId"],
                   body=json.dumps(Chercheur))
    progress_recorder.set_progress(10, 10)
    return Chercheur

@shared_task(bind=True)
def collecte_docs(self,  Chercheur):
    docs = hal.findPublications(Chercheur['halId_s'], 'authIdHal_s')
    progress_recorder = ProgressRecorder(self)
    progress_recorder.set_progress(0, 10, description='récupération des données HAL')
    # Insert documents collection
    for num, doc in enumerate(docs):
        progress_recorder.set_progress(num, len(docs))
        doc["_id"] = doc['docid']
        doc["validated"] = False

        doc["harvested_from"] = "researcher"

        doc["harvested_from_ids"] = []
        doc["harvested_from_label"] = []
        # try:
        #     doc["harvested_from_label"].append(dicoAcronym[row["labHalId"]])
        # except:
        #     doc["harvested_from_label"].append("non-labo")

        doc["harvested_from_ids"].append(Chercheur['halId_s'])
        # historique d'appartenance du docId
        # pour attribuer les bons docs aux chercheurs
        # harvet_history.append({'docid': doc['docid'], 'from': row['halId_s']})
        #
        # for h in harvet_history:
        #     if h['docid'] == doc['docid']:
        #         if h['from'] not in doc["harvested_from_ids"]:
        #             doc["harvested_from_ids"].append(h['from'])

        doc["records"] = []

        if 'doiId_s' in doc:
            tmp_unpaywall = unpaywall.getOa(doc['doiId_s'])
            if 'is_oa' in tmp_unpaywall: doc['is_oa'] = tmp_unpaywall['is_oa']
            if 'oa_status' in tmp_unpaywall: doc['oa_status'] = tmp_unpaywall['oa_status']
            if 'oa_host_type' in tmp_unpaywall: doc['oa_host_type'] = tmp_unpaywall['oa_host_type']

        doc["MDS"] = utils.calculateMDS(doc)

        try:
            shouldBeOpen = utils.shouldBeOpen(doc)
            if shouldBeOpen == 1:
                doc["shouldBeOpen"] = True
            if shouldBeOpen == -1:
                doc["shouldBeOpen"] = False

            if shouldBeOpen == 1 or shouldBeOpen == 2:
                doc['isOaExtra'] = True
            elif shouldBeOpen == -1:
                doc['isOaExtra'] = False
        except:
            print('publicationDate_tdate error ?')

        # if not init:
        #
        #     doc_param = {
        #         "query": {
        #             "match": {
        #                 "_id": doc["_id"]
        #             }
        #         }
        #     }
        #
        #     if not es.indices.exists(index=row["structSirene"] + "-" + row["labHalId"] + "-researchers-" + row[
        #         "ldapId"] + "-documents"):  # -researchers" + row["ldapId"] + "-documents
        #         print("exception ", row["labHalId"], row["ldapId"])
        #         break
        #     res = es.search(
        #         index=row["structSirene"] + "-" + row["labHalId"] + "-researchers-" + row["ldapId"] + "-documents",
        #         body=doc_param)  # -researchers" + row["ldapId"] + "-documents
        #
        #     if len(res['hits']['hits']) > 0:
        #         doc['validated'] = res['hits']['hits'][0]['_source']['validated']
        #
        #         if res['hits']['hits'][0]['_source']['modifiedDate_tdate'] != doc['modifiedDate_tdate']:
        #             doc["records"].append({'beforeModifiedDate_tdate': doc['modifiedDate_tdate'],
        #                                    'MDS': res['hits']['hits'][0]['_source']['MDS']})
        #
        #     else:
        #         doc["validated"] = False
    es = esConnector()
    res = helpers.bulk(
        es,
        docs,
        index= Chercheur["structSirene"]  + "-" + Chercheur["labHalId"] + "-researchers-" + Chercheur["ldapId"] + "-documents",
        # -researchers" + row["ldapId"] + "-documents
            )
    return docs # pas utile...

