import requests


def findDomains(idRef):

    r = requests.post('https://scanr-api.enseignementsup-recherche.gouv.fr/api/v2/publications/search',
                      json={"query": "idref" + idRef})

    count = r.json()['total']
    r = requests.post('https://scanr-api.enseignementsup-recherche.gouv.fr/api/v2/publications/search',
                      json={"query": "idref" + idRef, "pageSize": count})

    publications = r.json()

    domains = []

    if 'request' not in publications.keys():
        publications['results'] = []

    try:
        for publication in publications['results']:
            if "value" in publication.keys():
                if "domains" in publication['value'].keys():
                    for domain in publication['value']["domains"]:
                        if "label" in domain and "fr" in domain['label']:
                            domains.append(domain['label']['fr'])
    except Exception as e:
        print('Error in findDomains')
        print(e)

    unique_domains = []

    for domain in domains:
        unique = True
        for unique_domain in unique_domains:
            if domain == unique_domain['id']:
                unique_domain['weight'] += 1
                unique = False
        if unique:
            unique_domains.append({'id': domain, 'weight': 1})
    return sorted(unique_domains, key=lambda i: i['weight'], reverse=True)
