import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["HEAD", "GET", "DELETE", "PUT", "OPTIONS"],
)
adapter = HTTPAdapter(max_retries=retry_strategy)
http = requests.Session()
http.mount("https://", adapter)
http.mount("http://", adapter)


def getCitations(doi):
    """
    Récupération des citations d'un article
    """
    response = http.get("https://metrics-api.dimensions.ai/doi/" + doi)
    if response.status_code == 200:
        response = response.json()
        if "times_cited" in response:
            return {
                "times_cited": response["times_cited"],
                "field_citation_ratio": response["field_citation_ratio"],
            }
    return None
