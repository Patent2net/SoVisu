import requests


def get_embargo_duration(journal):

    api_key = "6569EC86-7B55-11EB-8F47-961C3DE2659A"
    endpoint = "https://v2.sherpa.ac.uk/cgi/retrieve/cgi/retrieve?api-key=" + api_key

    journal_r = requests.get(endpoint + '&item-type=publication&format=Json&filter=[["title","equals","' + journal + '"]]')
    journal_id = journal_r.json()['items'][0]['id']

    print(endpoint + '&item-type=publisher_policy&format=Json&filter=[["id","equals","' + str(journal_id) + '"]]')

    publisher_policy = journal_r.json()['items'][0]['publisher_policy'][0]['permitted_oa']

    p_type = 'published'

    for version in publisher_policy:
        for lang in version['article_version_phrases']:
            if lang['value'] == p_type and lang['language'] == 'en':
                if 'embargo' in version:
                    embargo_duration = version['embargo']

    try:
        embargo_duration
    except NameError:
        embargo_duration = None

    return embargo_duration
