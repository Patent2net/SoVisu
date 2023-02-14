def generate_countrys_fields(doc):
    """
    Enrichi les notices avec les champs country_collaboration qui fusionne :
        "deptStructCountry_s", --> Structure/regroupement d'équipes : Pays
        "labStructCountry_s", --> Structure/laboratoire : Pays
        "structCountry_s", --> Structure/regroupement d'institutions : Pays
        "structCountry_t",--> Structure : Pays ( copie de ce champ : structCountry_s) !!!!
        "rgrpInstStructCountry_s",--> Structure/regroupement d'institutions : Pays
        "rgrpLabStructCountry_s"--> Structure/regroupement de laboratoires : Pays
    el le champs country_origin fusionnant :
        country_s, --> Pays (Code ISO 3166)
        rteamStructCountry_s --> Structure/équipe de recherche : Pays
        instStructCountry_s -->  Structure/institution : Pays
    en se basant sur les métadonnées Hal du document
    """
    facet_fields_list = [
        "deptStructCountry_s",
        "labStructCountry_s",
        "structCountry_s",  # "structCountry_t",
        "rgrpInstStructCountry_s",
        "rgrpLabStructCountry_s",
    ]
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
    doc["country_collaboration"] = country_list_upper

    facet_fields_list = [
        "country_s",
        "rteamStructCountry_s",
        "instStructCountry_s",
        "publicationLocation_s",
    ]

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
        country_list_upper.remove("FR")
    else:
        pass

    if len(country_list_upper) == 0:
        country_list_upper = [""]
    # print(" fin de génération des champs country")
    return list(set(country_list_upper))
