import requests


from elasticHal.libs import dimensions
from requests.packages.urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

retry_strategy = Retry(
    total=3,
    backoff_factor=2,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["HEAD", "GET", "DELETE", "PUT", "OPTIONS"]
)
adapter = HTTPAdapter(max_retries=retry_strategy)
http = requests.Session()
http.mount("https://", adapter)
http.mount("http://", adapter)

def check_doi(doi):
    # Cette fonctionpermet de tester un DOI au travers d'une requete . Renvoie si False si le DOI est invalie renvoi True si le DOI  exist
    url = 'https://doi.org/' + doi
    try:
        res = http.get(url, timeout=50)

        if str(res) == "<Response [200]>":

            return True
        else:
            return False
    except:

        return False


def docs_enrichissement_doi(doc):
    # Cette Fonction permet de retourner la date de mise en open access de l'ensemble des documents contenu dans doc en fonction de leur DOI
    # La fonction test la validiter du DOI si le DOI n'est pas valide initialise le DOI vide, si le Doi existe teste la date de mise en open
    # acces du document sinon initialise la date de mise en open access vide
    # print("début docs_enrichissement_doi_date")
    #for index, doc in enumerate(docs):
    if "doiId_s" in doc.keys():  # Si Le Doi est renseigné dans le document pris en paramètre
        citations = dimensions.getCitations(doc["doiId_s"])
        if citations:
            doc["field_citation_ratio"] = citations["field_citation_ratio"]
            doc["times_cited"] = citations["times_cited"]
        url = "https://api.unpaywall.org/v2/"+doc["doiId_s"]+"?email=SOVisuHAL@univ-tln.fr"
        req = http.get(url, timeout=50)  # envoie une requête sur l'API Unpaywall pour récupérer des informations
        data = req.json()

        if req.status_code == 200:
            if "oa_status" in data.keys(): doc["oa_status"] = data['oa_status']
            if "is_oa" in data.keys():
                if data['is_oa'] == True:  # Test si le doi est en open access sur l'api Unpaywall
                    doc['is_oa'] = 'open access'
                    if data["first_oa_location"]["oa_date"] != None:
                        doc["date_depot_oa"] = (data["first_oa_location"]["oa_date"])
                    elif data["first_oa_location"]["updated"] != None:
                        doc["date_depot_oa"] = data["first_oa_location"]["updated"]
                    else:
                        pass # doc["date_depot_oa"] = ""   : elastic aime pas le changement de type
                else:
                    doc['is_oa'] = 'closed access'

        else:
            doc["doiId_sPasCorrect"] = check_doi(doc["doiId_s"])

        if 'publisher' not in data:
            doc["oa_host_type"] = 'open archive'

        elif 'has_repository_copy' not in data:
            doc["oa_host_type"] = 'editor'

        elif 'publisher' in data and 'has_repository_copy' in data:
            doc["oa_host_type"] = 'editor and open archive'

        elif not data['is_oa']:
            doc["oa_host_type"] = 'closed access'

        else:
            doc["oa_host_type"] = 'N/A'

    # initialisation des champs vide pour eviter les porblémes de mapping
    """
    for key in ["oa_status","is_oa","date_depot_oa","oa_host_type"]:
        if key not in  doc.keys():
            doc[key]=""
    """
    #print("fin docs_enrichissement_doi_date")
    return doc

