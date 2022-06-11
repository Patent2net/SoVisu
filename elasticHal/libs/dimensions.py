import requests

def getCitations(doi):
    response = requests.request("GET", "https://metrics-api.dimensions.ai/doi/" + doi)
    if response.status_code == 200:
        response = response.json()
        if "times_cited" in response:
            return {"times_cited": response['times_cited'], "field_citation_ratio": response['field_citation_ratio']}
    return None