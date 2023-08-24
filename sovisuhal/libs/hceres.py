import pandas as pd

from constants import SV_LAB_INDEX, SV_INDEX
from . import esActions

es = esActions.es_connector()


def common_data(list1, list2):
    """
    Renvoie la liste des éléments communs entre deux listes
    """
    result = False

    # traverse in the 1st list
    for x in list1:
        # traverse in the 2nd list
        for y in list2:
            # if one common
            if x == y:
                result = True
                return result

    return result


def sort_references(articles, struct_docid):
    """
    Classe les références récupérées dans un ordre défini pour le HCERES
    """
    # sort by lab
    # TODO: Add a way to filter by institution, in case where lab is affiliated to X institutions
    researchers_list = []

    query = {
        "bool": {
            "must": [
                {"match": {"sovisu_category": "searcher"}},
            ]
        }
    }

    res = es.search(index=SV_LAB_INDEX, query=query)

    res_cleaned = []
    for res in res["hits"]["hits"]:
        res_cleaned.append(res["_source"])
    print(res_cleaned)
    for rsr in res_cleaned:
        if struct_docid in rsr["sv_affiliation"]:
            researchers_list.append(rsr["halId_s"])

    sort_trigger = False

    hceres_art = []
    hceres_book = []
    hceres_conf = []
    hceres_hdr = []

    for article in articles:

        article["hasPhDCandidate"], article["team"] = article_has_phd_candidate_and_team(article)

        # TODO: Documents linked to laboratories don't have authorship field. Only searchers have it
        article["hasAuthorship"] = article_has_authorship_hceres(struct_docid, article)

        article["authfullName_s"] = ""

        article["volFull_s"] = ""

        if "serie_s" in article:
            if "issue_s" in article:
                article["volFull_s"] = article["serie_s"][0] + " " + article["issue_s"][0]
            else:
                article["volFull_s"] = article["serie_s"][0]

        if "journalTitle_s" not in article:
            article["journalTitle_s"] = ""

        if "openAccess_bool" in article:
            if (
                    article["openAccess_bool"] == "true"
                    or article["openAccess_bool"] == True
            ):
                article["openAccess_bool_s"] = "O"
            else:
                article["openAccess_bool_s"] = "N"

        if "conferenceStartDate_tdate" in article:
            tmp_start = article["conferenceStartDate_tdate"][0:9].split("-")
            if "conferenceEndDate_tdate" in article:
                tmp_end = article["conferenceEndDate_tdate"][0:9].split("-")
                article["conferenceDate_s"] = (
                        tmp_start[2]
                        + "-"
                        + tmp_start[1]
                        + "-"
                        + tmp_start[0]
                        + ", "
                        + tmp_end[2]
                        + "-"
                        + tmp_end[1]
                        + "-"
                        + tmp_end[0]
                )
            else:
                article["conferenceDate_s"] = tmp_start[2] + "-" + tmp_start[1] + "-" + tmp_start[0]
        else:
            if "conferenceEndDate_tdate" in article:
                tmp_end = article["conferenceEndDate_tdate"][0:9].split("-")
                article["conferenceDate_s"] = tmp_end[2] + "-" + tmp_end[1] + "-" + tmp_end[0]

        if "defenseDate_tdate" in article:
            article["defenseDate_tdate_s"] = article["defenseDate_tdate"][0:9]

        article["title_s"] = article["title_s"][0]
        if "authFirstName_s" in article.keys():
            if len(article["authFirstName_s"]) > 0:
                for i in range(len(article["authFirstName_s"])):
                    article["authfullName_s"] += (
                            article["authLastName_s"][i].upper()
                            + " "
                            + article["authFirstName_s"][i]
                            + ", "
                    )
            else:
                article["authfullName_s"] = ", ".join(article["authFullName_s"])
        else:
            article["authfullName_s"] = ", ".join(article["authFullName_s"])

        article["authfullName_s"] = article["authfullName_s"][:-2]
        if (
                "docType_s" not in article.keys()
        ):  # Encore des exeptions... Est que c'est ponctuel le temps que la base mouline ????
            if "journalTitle_s" in article.keys():
                article["docType_s"] = "ART"
        if sort_trigger:
            if "authIdHal_s" in article:
                if common_data(researchers_list, article["authIdHal_s"]):
                    # colloque et posters
                    if article["docType_s"] == "COMM" or article["docType_s"] == "POSTER":
                        hceres_conf.append(article)
                    # art
                    if article["docType_s"] == "ART":
                        hceres_art.append(article)
                    # ouvrages, chapitres d'ouvrages et directions d'ouvrages
                    if (
                            article["docType_s"] == "COUV"
                            or article["docType_s"] == "DOUV"
                            or article["docType_s"] == "OUV"
                    ):
                        hceres_book.append(article)
                    # hdr
                    if article["docType_s"] == "HDR":
                        print(article)
                        hceres_hdr.append(article)
        else:
            # colloque et posters
            if article["docType_s"] == "COMM" or article["docType_s"] == "POSTER":
                hceres_conf.append(article)
            # art
            if article["docType_s"] == "ART":
                hceres_art.append(article)
            # ouvrages, chapitres d'ouvrages et directions d'ouvrages
            if (
                    article["docType_s"] == "COUV"
                    or article["docType_s"] == "DOUV"
                    or article["docType_s"] == "OUV"
            ):
                hceres_book.append(article)
            # hdr
            if article["docType_s"] == "HDR":
                print(article)
                hceres_hdr.append(article)

    art_df = create_sorted_dataframe(hceres_art)
    book_df = create_sorted_dataframe(hceres_book)
    conf_df = create_sorted_dataframe(hceres_conf)
    hceres_df = create_sorted_dataframe(hceres_hdr)

    return art_df, book_df, conf_df, hceres_df


def article_has_phd_candidate_and_team(article):
    has_phd_candidate = False
    team = ""
    if "authIdHal_s" in article:
        for authIdHal_s in article["authIdHal_s"]:
            exist = es.exists(index=SV_INDEX, id=authIdHal_s)

            if exist:
                res = es.get(index=SV_INDEX, id=authIdHal_s)
                res = res["_source"]

                if res.get("function") == "Doctorant":
                    has_phd_candidate = True

                if "axis" in res:
                    axis = res["axis"].replace("axis", "")
                    team = team + axis + " ; "

        if len(team) > 2:
            team = team[:-2]

    if has_phd_candidate:
        phd_candidate_value = "O"
    else:
        phd_candidate_value = "N"

    return phd_candidate_value, team


def article_has_authorship_hceres(struct_docid, article):

    has_authorship = False

    if "authorship" in article:
        for authorship in article["authorship"]:
            # authFullName_s qui est en fait halId_s mais pas toujours
            try:
                halid_s = authorship["authFullName_s"]

            except IndexError:
                halid_s = authorship["halId_s"]

            res = es.get(index=SV_INDEX, id=halid_s)
            if len(res["source"]) > 0 and res["_source"]["docid"] == struct_docid:
                has_authorship = True

    if has_authorship:
        authorship_value = "O"
    else:
        authorship_value = "N"

    return authorship_value


def create_sorted_dataframe(data):
    dataframe = pd.DataFrame(data)
    if len(dataframe.index) > 0:
        dataframe = dataframe.sort_values(by=["publicationDateY_i"])
    return dataframe
