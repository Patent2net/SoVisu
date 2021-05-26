import requests

def getOa(doi):

    req = requests.get('https://api.unpaywall.org/v2/' + doi + '?email=alarictabaries@gmail.com')

    if req.status_code == 200:
        data = req.json()

        if data['is_oa'] == True:
            data['is_oa'] = 'open access'
        else:
            data['is_oa'] = 'closed access'

        if 'publisher' not in data:
            oa_host_type = 'open archive'
        elif 'has_repository_copy' not in data:
            oa_host_type = 'editor'
        elif 'publisher' in data and 'has_repository_copy' in data:
            oa_host_type = 'editor and open archive'
        elif data['is_oa'] == False:
            oa_host_type = 'closed access'

        return {'is_oa': data['is_oa'],'oa_status': data['oa_status'], 'oa_host_type': oa_host_type}

    else:
        print(req, "unpaywall")
        return {}