# from libs import hal, utils, unpaywall, scanR

from sovisuhal.libs.archivesOuvertes import get_concepts_and_keywords
from sovisuhal.libs.libsElastichal import get_aurehal
from sovisuhal.libs import utils, hal, unpaywall, archivesOuvertes
from elasticsearch import helpers
import json
import datetime

from . import esActions

try:
    from decouple import config
    from ldap3 import Server, Connection, ALL
    from uniauth.decorators import login_required

    mode = config("mode")  # Prod --> mode = 'Prod' en env Var

except:
    from django.contrib.auth.decorators import login_required

    mode = "Dev"
    structId = "198307662"  # UTLN


# from celery import shared_task
# from celery_progress.backend import ProgressRecorder


# struct = "198307662"


# @shared_task(bind=True)
def indexe_chercheur(ldapid, labo_accro, labhalid, idhal, idref, orcid):  # self,
    es = esActions.es_connector()
    #   progress_recorder = ProgressRecorder(self)
    #   progress_recorder.set_progress(0, 10, description='récupération des données LDAP')
    if mode == "Prod":
        server = Server('ldap.univ-tln.fr', get_info=ALL)
        conn = Connection(server, 'cn=Sovisu,ou=sysaccount,dc=ldap-univ-tln,dc=fr', config('ldappass'),
                          auto_bind=True)  # recup des données ldap
        conn.search('dc=ldap-univ-tln,dc=fr', '(&(uid=' + ldapid + '))',
                    attributes=['displayName', 'mail', 'typeEmploi', 'ustvstatus', 'supannaffectation',
                                'supanncodeentite', 'supannEntiteAffectationPrincipale', 'labo'])
        dico = json.loads(conn.response_to_json())['entries'][0]
        structid = config("structId")
    else:
        dico = {'attributes': {'displayName': 'REYMOND David', 'labo': [], 'mail': ['david.reymond@univ-tln.fr'],
                               'supannAffectation': ['IMSIC', 'IUT TC'], 'supannEntiteAffectationPrincipale': 'IUTTCO',
                               'supanncodeentite': [], 'typeEmploi': 'Enseignant Chercheur Titulaire',
                               'ustvStatus': ['OFFI']},
                'dn': 'uid=dreymond,ou=Personnel,ou=people,dc=ldap-univ-tln,dc=fr'}
        structid = "198307662"
        ldapid = 'dreymond'
    labo = labhalid

    extrait = dico['dn'].split('uid=')[1].split(',')
    chercheur_type = extrait[1].replace('ou=', '')
    suppan_id = extrait[0]
    if suppan_id != ldapid:
        print("aille", ldapid, ' --> ', ldapid)
    nom = dico['attributes']['displayName']
    emploi = dico['attributes']['typeEmploi']
    mail = dico['attributes']['mail']
    if 'supannAffectation' in dico['attributes'].keys():
        supann_affect = dico['attributes']['supannAffectation']
    if 'supannEntiteAffectationPrincipale' in dico['attributes'].keys():
        supann_princ = dico['attributes']['supannEntiteAffectationPrincipale']
    else:
        supann_princ = []
    if not len(nom) > 0:
        nom = ['']
    elif not len(emploi) > 0:
        emploi = ['']
    elif not len(mail) > 0:
        mail = ['']

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
    chercheur["firstName"] = chercheur['name'].split(' ')[1]
    chercheur["lastName"] = chercheur['name'].split(' ')[0]

    # Chercheur["aurehalId"]

    # creation des index
    #  progress_recorder.set_progress(5, 10, description='creation des index')
    if not es.indices.exists(index=structid + "-structures"):
        es.indices.create(index=structid + "-structures")
    if not es.indices.exists(index=structid + "-" + labo + "-researchers"):
        es.indices.create(index=structid + "-" + labo + "-researchers")
        es.indices.create(
            index=structid + "-" + labo + "-researchers-" + ldapid + "-documents")  # -researchers" + row["ldapId"] + "-documents
    else:
        if not es.indices.exists(index=structid + "-" + labo + "-researchers-" + ldapid + "-documents"):
            es.indices.create(
                index=structid + "-" + labo + "-researchers-" + ldapid + "-documents")  # -researchers" + row["ldapId"] + "-documents" ?

    chercheur["structSirene"] = structid
    chercheur["labHalId"] = labo
    chercheur["validated"] = False
    chercheur["ldapId"] = ldapid
    chercheur["Created"] = datetime.datetime.now().isoformat()

    # New step ?

    if idhal != '':
        aurehal = get_aurehal(idhal)
        # integration contenus
        archives_ouvertes_data = get_concepts_and_keywords(aurehal)
    else:
        pass
        # retourne sur check() ?
    chercheur["halId_s"] = idhal
    chercheur["validated"] = False
    chercheur["aurehalId"] = aurehal  # heu ?
    chercheur["concepts"] = archives_ouvertes_data['concepts']
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
    res = es.index(index=chercheur["structSirene"] + "-" + chercheur["labHalId"] + "-researchers",
                   id=chercheur["ldapId"],
                   body=json.dumps(chercheur))  # ,
    # timestamp=datetime.datetime.now().isoformat()) #pour le suvi modification de ingest plutôt cf. https://kb.objectrocket.com/elasticsearch/how-to-create-a-timestamp-field-for-an-elasticsearch-index-275
    # progress_recorder.set_progress(10, 10)
    print("statut de la création d'index: ", res['result'])
    return chercheur


def propage_concepts(struct_sirene, ldapid, labo_accro, labhalid):
    # for row in csv_reader:
    row = dict()
    # print(row['acronym'])
    es = esActions.es_connector(mode)
    field = "labHalId"
    rsr_param = esActions.scope_p(field, labhalid)

    res = es.search(index=row['structSirene'] + "-" + row["halStructId"] + "-researchers", body=rsr_param)
    # tous ces champs (lignes qui suit) sont là (ligne précédente à adapter) ou dans structSirene + "-" +labHalId +
    # "-" + ldapId +"-researchers" ? structSirene, ldapId, name, type, function, mail, lab, supannAffectation,
    # supannEntiteAffectationPrincipale, halId_s, labHalId, idRef, structDomain, firstName, lastName, aurehalId

    # car il faudrait que l'update ne (cf. ligne 196)
    # après le reste devrait rouler même si je ne comprends pas pourquoi ce matin
    # j'ai dû modifier views pour cause de l'abscence de state dans la boucle équivalent pour l'affichage 'labo' ?
    row['guidingKeywords'] = []

    # Build laboratory skills
    tree = {'id': 'Concepts', 'children': []}

    for rsr in res['hits']['hits']:

        concept = rsr['_source']['concepts']

        if len(concept) > 0:

            for child in concept['children']:

                if child['state'] == 'invalidated':
                    tree = utils.append_to_tree(child, rsr['_source'], tree, 'invalidated')
                else:
                    tree = utils.append_to_tree(child, rsr['_source'], tree)
                if 'children' in child:
                    for child1 in child['children']:

                        if child1['state'] == 'invalidated':
                            tree = utils.append_to_tree(child1, rsr['_source'], tree, 'invalidated')
                        else:
                            tree = utils.append_to_tree(child1, rsr['_source'], tree)

                        if 'children' in child1:
                            for child2 in child1['children']:

                                if child2['state'] == 'invalidated':
                                    tree = utils.append_to_tree(child2, rsr['_source'], tree, 'invalidated')
                                else:
                                    tree = utils.append_to_tree(child2, rsr['_source'], tree)

    row['concepts'] = tree
    row["Created"] = datetime.datetime.now().isoformat()
    # Insert laboratory data
    # est-ce qu'update est destructeur ?
    res = es.index(index=row['structSirene'] + "-" + row["halStructId"] + "-laboratories", id=row['halStructId'],
                   body=json.dumps(row))
    # timestamp=datetime.datetime.now().isoformat())


# @shared_task(bind=True)
def collecte_docs(chercheur):  # self,

    init = False  # If True, data persistence is lost when references are updated
    docs = hal.find_publications(chercheur['halId_s'], 'authIdHal_s')
    es = esActions.es_connector()
    #  progress_recorder = ProgressRecorder(self)
    #  progress_recorder.set_progress(0, 10, description='récupération des données HAL')
    # Insert documents collection
    for num, doc in enumerate(docs):
        #     progress_recorder.set_progress(num, len(docs))
        doc["_id"] = doc['docid']
        doc["validated"] = True

        doc["harvested_from"] = "researcher"

        doc["harvested_from_ids"] = []
        doc["harvested_from_label"] = []
        # try:
        #     doc["harvested_from_label"].append(dicoAcronym[row["labHalId"]])
        # except:
        #     doc["harvested_from_label"].append("non-

        doc["authorship"] = []

        authhalid_s_filled = []
        if "authId_i" in doc:
            for auth in doc["authId_i"]:
                try:
                    aurehal = archivesOuvertes.get_halid_s(auth)
                    authhalid_s_filled.append(aurehal)
                except:
                    authhalid_s_filled.append("")

        authors_count = len(authhalid_s_filled)
        i = 0
        for auth in authhalid_s_filled:
            i += 1
            if i == 1 and auth != "":
                doc["authorship"].append({"authorship": "firstAuthor", "authFullName_s": auth})
            elif i == authors_count and auth != "":
                doc["authorship"].append({"authorship": "lastAuthor", "authFullName_s": auth})

        doc["harvested_from_ids"].append(chercheur['halId_s'])

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
            tmp_unpaywall = unpaywall.get_oa(doc['doiId_s'])
            if 'is_oa' in tmp_unpaywall: doc['is_oa'] = tmp_unpaywall['is_oa']
            if 'oa_status' in tmp_unpaywall: doc['oa_status'] = tmp_unpaywall['oa_status']
            if 'oa_host_type' in tmp_unpaywall: doc['oa_host_type'] = tmp_unpaywall['oa_host_type']

        doc["MDS"] = utils.calculate_mds(doc)

        try:
            should_be_open = utils.should_be_open(doc)
            if should_be_open == 1:
                doc["shouldBeOpen"] = True
            if should_be_open == -1:
                doc["shouldBeOpen"] = False

            if should_be_open == 1 or should_be_open == 2:
                doc['isOaExtra'] = True
            elif should_be_open == -1:
                doc['isOaExtra'] = False
        except:
            print('publicationDate_tdate error ?')
        doc['Created'] = datetime.datetime.now().isoformat()

        if not init:
            field = "_id"
            doc_param = esActions.scope_p(field, doc["_id"])

            if not es.indices.exists(index=chercheur["structSirene"] + "-" + chercheur["labHalId"] + "-researchers-" + chercheur["ldapId"] + "-documents"):  # -researchers" + row["ldapId"] + "-documents
                print("exception ", chercheur["labHalId"], chercheur["ldapId"])

            res = es.search(
                index=chercheur["structSirene"] + "-" + chercheur["labHalId"] + "-researchers-" + chercheur[
                    "ldapId"] + "-documents",
                body=doc_param)  # -researchers" + row["ldapId"] + "-documents

            if len(res['hits']['hits']) > 0:
                doc['validated'] = res['hits']['hits'][0]['_source']['validated']
                if 'authorship' in res['hits']['hits'][0]['_source']:
                    doc['authorship'] = res['hits']['hits'][0]['_source']['authorship']

                if res['hits']['hits'][0]['_source']['modifiedDate_tdate'] != doc['modifiedDate_tdate']:
                    doc["records"].append({'beforeModifiedDate_tdate': doc['modifiedDate_tdate'],
                                           'MDS': res['hits']['hits'][0]['_source']['MDS']})

            else:
                doc["validated"] = True

    res = helpers.bulk(
        es,
        docs,
        index=chercheur["structSirene"] + "-" + chercheur["labHalId"] + "-researchers-" + chercheur[
            "ldapId"] + "-documents"
        # -researchers" + row["ldapId"] + "-documents
    )
    """
    print("res is stocked in")
    print(Chercheur["structSirene"] + "-" + Chercheur["labHalId"] + "-researchers-" + Chercheur["ldapId"] +
     "-documents")

    res = helpers.bulk(
        es,
        docs,
        index= Chercheur["structSirene"] + "-" + Chercheur["labHalId"] + "-laboratories-documents"
    )
    print("res lab is stocked in")
    print(Chercheur["structSirene"] + "-" + Chercheur["labHalId"] + "-laboratories-documents")
    """
    # return docs # pas utile...

    return chercheur  # au cas où