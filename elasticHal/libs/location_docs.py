import requests


def generate_countrys_fields(doc):

    facet_fields_list = ["deptStructCountry_s", "labStructCountry_s", "structCountry_s", "structCountry_t",
                         "rgrpInstStructCountry_s", "rgrpLabStructCountry_s", ]
    country_list = list()
    for facet in facet_fields_list:
        if facet in doc.keys():
            if type(doc[facet]) == list:
                country_list.extend(doc[facet])
            else:
                country_list.append(doc[facet])
        else:
            doc[facet] = [""]

    country_list = list(set(country_list))
    country_list_upper = [country.upper() for country in country_list]
    if len(country_list_upper) == 0:
        country_list_upper = [""]
    doc["country_origin"] = country_list_upper

    facet_fields_list = ["country_s", "country_t", "rteamStructCountry_s", "instStructCountry_s"]

    country_list = list()
    for facet in facet_fields_list:
        if facet in doc.keys():
            if type(doc[facet]) == list:
                country_list.extend(doc[facet])
            else:
                country_list.append(doc[facet])
        else:
            doc[facet] = [""]

    country_list = list(set(country_list))
    country_list_upper = [country.upper() for country in country_list]
    if "FR" in country_list_upper:
        country_list_upper.remove('FR')
    else:
        pass

    if len(country_list_upper) == 0:
        country_list_upper = [""]
    # print(" fin de génération des champs country")
    return country_list_upper


def extract_locations_from_docid_list(docid):
    facet_fields_list = ["country_s", "deptStructCountry_s", "labStructCountry_s", "location",
                         "rgrpInstStructCountry_s", "rgrpLabStructCountry_s", "rteamStructCountry_s",
                         "deptStructAddress_s", "instStructCountry_s", "structCountry_s", "structCountry_t"]
    url = 'https://api.archives-ouvertes.fr/search/?q=docid:"' + str(docid) + '"&wt=json&indent=true'
    for facet_field in facet_fields_list:
        url = url + "&facet=true&facet.field=" + facet_field
        # https://api.archives-ouvertes.fr/search/?q=docid:854050&wt=json&indent=true&facet=true&facet.field=publicationLocation_s

    res = requests.get(url, timeout=50).json()

    country_list = list()
    for facet_field in facet_fields_list:
        pre_element = []
        try:
            if facet_field in res["facet_counts"]["facet_fields"]:
                for element in res["facet_counts"]["facet_fields"][facet_field]:
                    try:
                        if int(element) == 1:
                            country_list.append(pre_element)
                        else:
                            pass

                    except:
                        pass
                    pre_element = element
            else:
                print("ERROR" + facet_field)
        except Exception as e:
            print(e)

    country_list = list(set(country_list))
    country_list_upper = [country.upper() for country in country_list]

    return country_list_upper
