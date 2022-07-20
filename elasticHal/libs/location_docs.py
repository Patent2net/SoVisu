import requests


def generate_countrys_fields(doc):
    """
    Enrichi les données avec les champs "deptStructCountry_s", "labStructCountry_s", "structCountry_s", "structCountry_t","rgrpInstStructCountry_s", "rgrpLabStructCountry_s" en se basant sur les données du document
    :param doc: document à enrichir
    :return: document enrichi
    """
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
