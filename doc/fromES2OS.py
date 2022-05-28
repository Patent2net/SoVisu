from elasticsearch import Elasticsearch
from opensearchpy import OpenSearch
import datetime
# Custom libs
#from sovisuhal.libs import esActions
#from elasticHal.libs import archivesOuvertes, utils


#from elasticHal.models import Structure, Laboratory, Researcher

host = 'localhost'
port = 9400
auth = ('admin', 'admin') # For testing only. Don't store credentials in code.
# ca_certs_path = '/full/path/to/root-ca.pem' # Provide a CA bundle if you use intermediate CAs with your root CA.

OSclient = OpenSearch(
    hosts = [{'host': host, 'port': port}],
    http_compress = True, # enables gzip compression for request bodies
    http_auth = auth,
    # client_cert = client_cert_path,
    # client_key = client_key_path,
    use_ssl = True,
    verify_certs = False,
    ssl_assert_hostname = False,
    ssl_show_warn = False#,
    #ca_certs = ca_certs_path
)


# Connect to DB

def es_connector(mode=True):
    # if mode == "Prod":
    #
    #     secret = config('ELASTIC_PASSWORD')
    #     # context = create_ssl_context(cafile="../../stackELK/secrets/certs/ca/ca.crt")
    #     es = Elasticsearch('localhost',
    #                        http_auth=('elastic', secret),
    #                        scheme="http",
    #                        port=9200,
    #                        # ssl_context=context,
    #                        timeout=10)
    # else:
    #
    es = Elasticsearch([{'host': 'localhost', 'port': 9200}])
    return es

def scope_all():
    scope = {
        "query": {
            "match_all": {}
        }
    }
    return scope


# Use that base code in other files to use scope_p function: variable_name = esActions.scope_p(scope_field, scope_value)
def scope_p(scope_field, scope_value):
    scope = {
        "query": {
            "match": {
                scope_field: scope_value
            }
        }
    }
    return scope

es = es_connector()

# memo des pbs.
# choix fait de se poser sur le ldapid
# si deux meme ldapid dans des index chercheurs différents alors
# memo du plus recent created seulement
scope_param = scope_all()
count = es.count(index="*-researchers", body=scope_param)['count']
res = es.search(index="*-researchers", body=scope_param, size=count)
chercheurs = res['hits']['hits']

ldapList= [cher['_source']['ldapId'] for cher in chercheurs]
doublons =  [cher for cher in chercheurs if ldapList .count(cher['_source']['ldapId']) >1]
cpt = 0
Vus, lstRetenus = [], []
for ind, doudou in enumerate(doublons):
    if "Created" in doudou['_source'] .keys():
        dateCrea = doudou['_source']["Created"]
        if doudou['_source']['ldapId'] not in Vus:
            Vus .append(doudou['_source']['ldapId'])
            retenu = doudou
            if ind< len(doublons)-1:
                Autres = [doub for doub in doublons [ind+1:] if doub ['_source']['ldapId'] == doudou ['_source']['ldapId']]
                for dub in Autres:
                    if dub ['_source']["Created"] > dateCrea:
                        retenu = dub
            lstRetenus .append(retenu)

        else:
            pass
    else:
        #pas venu depuis changement de mode avec Created
        Autres = [doub for doub in doublons[ind + 1:] if doub['_source']['ldapId'] == doudou['_source']['ldapId']]
        if len(Autres) == 0:
            doudou['_source']["Created"] = datetime.now().isoformat()
            lstRetenus.append(doudou)
print (len(lstRetenus), " sur ", len(doublons), " et ", len(set(ldapList))," ldapId uniques ")
deDoub = [cher['_source']['ldapId'] for cher in lstRetenus]
# print("__name__ value is : ", __name__)
scope_param = scope_all()
res = es.search(index="*-structures", body=scope_param)#, filter_path=["hits.hits._source.structSirene"])
machin = res['hits']['hits']
for structu in machin:
    print (structu)
    index_name = structu['_index']
    id = structu['_id']
    #OSclient.indices.delete(index=index_name)
    response = OSclient.indices.create(index_name)
    print("creation ", index_name)
    response = OSclient.index(index=index_name, body=structu['_source'], id=id, refresh=True)
    print(response, "remplissage")
    body = structu['_source']
    scope_param = scope_all()
    response =OSclient.search(scope_param,index=index_name)
    print(response, "check")
    struct = id
    # init esLaboratories
    count = es.count(index=struct + "*-laboratories", body=scope_param)['count']
    res = es.search(index=struct + "*-laboratories", body=scope_param, size=count)
    esLaboratories = res['hits']['hits']

    for lab in esLaboratories:
        print (lab)
        response = OSclient.indices.create(lab['_index'])
        response = OSclient.index(index=lab['_index'], body=lab['_source'], id=lab ['_id'], refresh=True)
        if response ['_shards']['successful']:
            print (lab['_id'] + " " + lab['_source']['acronym'] + ' créé')
        else:
            print (response)
        indexLabDoc =lab['_index'] + "-documents"
        # Remplissage des docs
        count = es.count(index=indexLabDoc, body=scope_param)['count']
        res = es.search(index=indexLabDoc, body=scope_param, size=count)
        esDocs = res['hits']['hits']
        ## création index doc
        response = OSclient.indices.create(indexLabDoc)
        if response['acknowledged']:
            print(indexLabDoc + ' créé')
        else:
            print (response)
        cpt =0
        for doc in esDocs:
            cpt +=1
            OSclient.index(index=indexLabDoc, body=doc ['_source'], id=doc['_id'], refresh=True)
        print (cpt, ' docs indexés sur ', count)
        # Récup des chercheurs
        indexLabCher = structu['_id'] + '-' + lab['_source']['halStructId'] + "-researchers"
        count = es.count(index=indexLabCher, body=scope_param)['count']
        res = es.search(index=indexLabCher, body=scope_param, size=count)
        esChers = res['hits']['hits']
        response = OSclient.indices.create(indexLabCher)
        if response['acknowledged']:
            print(indexLabCher + ' créé')
        cpt = 0
        for cher in esChers:
            if 'ldap' in cher['_source'] .keys():
                if cher['_source']['ldap'] not in deDoub:
                    OSclient.index(index=indexLabCher, body=cher['_source'], id=cher['_id'], refresh=True)
                    if response['_shards']['successful']:
                        print(cher['_id'] + " " + cher['_source']['ldap'] + ' indexé')
                    else:
                        print(response)
                else:
                    pass # on les traitera à la fin
            else: #cas AMU
                OSclient.index(index=indexLabCher, body=cher['_source'], id=cher['_id'], refresh=True)
                if response['_shards']['successful']:
                    print(cher['_id'] + " " + cher['_source']['ldap'] + ' indexé')
                else:
                    print(response)
            indexDocCher=indexLabCher + "-documents"
            # recup des doc chercheurs
            count = es.count(index=indexDocCher, body=scope_param)['count']
            res = es.search(index=indexDocCher, body=scope_param, size=count)
            esResearchersDocs = res['hits']['hits']
            response = OSclient.indices.create(indexDocCher)
            if response['acknowledged']:
                print(indexDocCher + ' créé')
            cpt =0
            for doc in esResearchersDocs:
                cpt += 1
                OSclient.index(index=indexDocCher, body=doc['_source'], id=doc['_id'], refresh=True)
            print(cpt, ' docs indexés sur ', count)
            #
        #
        #
for cher in lstRetenus:
    OSclient.index(index=cher['_index'], body=cher['_source'], id=cher['_id'], refresh=True)
    if response['acknowledged']:
        print(cher['_id'] + " " + cher['_source']['ldap'] + ' indexé et dédoublonné')
    else:
        print(response)