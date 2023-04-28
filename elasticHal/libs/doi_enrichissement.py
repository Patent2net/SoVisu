import requests
from requests.adapters import HTTPAdapter, MaxRetryError
from urllib3.exceptions import ReadTimeoutError
from urllib3.util.retry import Retry

from elasticHal.libs import dimensions

retry_strategy = Retry(
    total=3,
    backoff_factor=2,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["HEAD", "GET", "DELETE", "PUT", "OPTIONS"],
)
adapter = HTTPAdapter(max_retries=retry_strategy)
http = requests.Session()
http.mount("https://", adapter)
http.mount("http://", adapter)


def check_doi(doi):
    """
    La fonction plancte avec une erreur sur certains URL qui n'est pas attrapée par le try except//
    Vérifie si le doi renseigné existe dans la base de données de doi.org
    """
    # Cette fonction permet de tester un DOI au travers d'une requête.
    # Renvoie si True si le DOI est invalide renvoi True sinon

    if not doi.startswith("http"):
        url = "https://doi.org/" + doi
    else:
        url = doi
    connect_timeout = 6
    read_timeout = 10
    try:
        res = requests.get(
            url, timeout=(connect_timeout, read_timeout), verify=False
        )  # TRES MAUVAIS CHOIX ICI...
    except TimeoutError:
        return True
    except MaxRetryError:
        return True
    except ReadTimeoutError as e:
        print(url, e)
        return True
    else:
        if str(res) == "<Response [200]>":
            return False
        else:
            return True


def docs_enrichissement_doi(doc):
    """
    Enrichissement des documents avec les informations provenant du DOI

    """
    # for index, doc in enumerate(docs):
    if "doiId_s" in doc.keys():  # Si Le Doi est renseigné dans le document pris en paramètre
        citations = dimensions.getCitations(doc["doiId_s"])
        if citations:
            doc["field_citation_ratio"] = citations["field_citation_ratio"]
            doc["times_cited"] = citations["times_cited"]
        url = "https://api.unpaywall.org/v2/" + doc["doiId_s"] + "?email=SOVisuHAL@univ-tln.fr"
        req = http.get(
            url, timeout=50
        )  # envoie une requête sur l'API Unpaywall pour récupérer des informations
        data = req.json()

        if req.status_code == 200:
            if "oa_status" in data.keys():
                doc["oa_status"] = data["oa_status"]
            if "is_oa" in data.keys():
                if data["is_oa"] is True:  # Test si le doi est en open access sur l'api Unpaywall
                    doc["is_oa"] = "open access"
                    if data["first_oa_location"]["oa_date"] is not None:
                        doc["date_depot_oa"] = data["first_oa_location"]["oa_date"]
                    elif data["first_oa_location"]["updated"] is not None:
                        doc["date_depot_oa"] = data["first_oa_location"]["updated"]
                    else:
                        pass  # doc["date_depot_oa"] = ""   : elastic aime pas le changement de type
                else:
                    doc["is_oa"] = "closed access"

        elif (
            "doiId_sPasCorrect" in doc.keys()
        ):  # Faudra Virer çà un jour ou remettre en route la collecte
            doc.pop("doiId_sPasCorrect", None)
            # doc["doiId_sPasCorrect"] = check_doi(doc["doiId_s"])

        if "publisher" not in data:
            doc["oa_host_type"] = "open archive"

        elif "has_repository_copy" not in data:
            doc["oa_host_type"] = "editor"

        elif "publisher" in data and "has_repository_copy" in data:
            doc["oa_host_type"] = "editor and open archive"

        elif not data["is_oa"]:
            doc["oa_host_type"] = "closed access"

        else:
            doc["oa_host_type"] = "N/A"

    return doc
