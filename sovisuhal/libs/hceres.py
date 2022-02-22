import pandas as pd

from . import esActions

es = esActions.es_connector()


def common_data(list1, list2):
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

def sortReferences(articles, halStructId):

    # sort by lab
    utln_rsr = []
    amu_rsr = []

    universities = ["198307662", "130015332"]

    sort_param = esActions.scope_p("labHalId", halStructId)
    for univ in universities:
        res = es.search(index=univ + "-*-researchers", body=sort_param)
        for rsr in res['hits']['hits']:
            if univ == "198307662":
                utln_rsr.append(rsr['_source']['halId_s'])
            elif univ == "130015332":
                amu_rsr.append(rsr['_source']['halId_s'])

    sort_trigger = False

    hceres_art = []
    hceres_book = []
    hceres_conf = []
    hceres_hdr = []

    for article in articles:

        article["team"] = ""

        hasPhDCandidate = False
        if "authIdHal_s" in article:
            for authIdHal_s in article["authIdHal_s"]:

                field = "halId_s"
                doc_param = esActions.scope_p(field, authIdHal_s)
                doc_param = {
                    "query": {
                        "bool": {
                            "must": [
                                {
                                    "match_phrase": {
                                        "halId_s": authIdHal_s
                                    }
                                },
                                {
                                    "match": {
                                        "labHalId": halStructId
                                    }
                                }
                            ]
                        }
                    }
                }

                res = es.search(index="*-researchers", body=doc_param)

                if len(res['hits']['hits']) > 0:

                    if 'function' in res['hits']['hits'][0]['_source'] and res['hits']['hits'][0]['_source']['function'] == "Doctorant":
                        hasPhDCandidate = True

                    if 'axis' in res['hits']['hits'][0]['_source']:
                        axis = res['hits']['hits'][0]['_source']['axis'].replace("axis", "")
                        article["team"] = article["team"] + axis + " ; "

            if len(article["team"]) > 2:
                article["team"] = article["team"][:-2]

        if hasPhDCandidate:
            article["hasPhDCandidate"] = "O"
        else:
            article["hasPhDCandidate"] = "N"

        hasAuthorship = False

        if "authorship" in article:
            for authorship in article["authorship"]:
                field = "halId_s"
                # authFullName_s qui est en fait halId_s
                doc_param = esActions.scope_p(field, authorship["authFullName_s"])
                doc_param = {
                    "query": {
                        "bool": {
                            "must": [
                                {
                                    "match_phrase": {
                                        "halId_s": authorship["authFullName_s"]
                                    }
                                },
                                {
                                    "match": {
                                        "labHalId": halStructId
                                    }
                                }
                            ]
                        }
                    }
                }

                res = es.search(index="*-researchers", body=doc_param)
                if len(res['hits']['hits']) > 0 and res['hits']['hits'][0]['_source']['labHalId'] == halStructId:
                    hasAuthorship = True

        if hasAuthorship:
            article["hasAuthorship"] = "O"
        else:
            article["hasAuthorship"] = "N"

        article["authfullName_s"] = ""

        article["volFull_s"] = ""

        if "serie_s" in article:
            if "issue_s" in article:
                article["volFull_s"] = article["serie_s"][0] + " " + article["issue_s"][0]
            else:
                article["volFull_s"] = article["serie_s"][0]

        if "journalTitle_s" not in article:
            article["journalTitle_s"] = ""

        if 'openAccess_bool' in article:
            if article['openAccess_bool'] == "true" or article['openAccess_bool'] == True:
                article["openAccess_bool_s"] = "O"
            else:
                article["openAccess_bool_s"] = "N"

        if 'conferenceStartDate_tdate' in article:
            tmp_start = article["conferenceStartDate_tdate"][0:9].split("-")
            if 'conferenceEndDate_tdate' in article:
                tmp_end = article["conferenceEndDate_tdate"][0:9].split("-")
                article["conferenceDate_s"] = tmp_start[2] + "-" + tmp_start[1] + "-" + tmp_start[0] + ", " + tmp_end[
                    2] + "-" + tmp_end[1] + "-" + tmp_end[0]
            else:
                article["conferenceDate_s"] = tmp_start[2] + "-" + tmp_start[1] + "-" + tmp_start[0]
        else:
            if 'conferenceEndDate_tdate' in article:
                article["conferenceDate_s"] = tmp_end[2] + "-" + tmp_end[1] + "-" + tmp_end[0]

        if "defenseDate_tdate" in article:
            article["defenseDate_tdate_s"] = article["defenseDate_tdate"][0:9]

        article["title_s"] = article["title_s"][0]

        for i in range(len(article["authFirstName_s"])):
            article["authfullName_s"] += article["authLastName_s"][i].upper() + " " + article["authFirstName_s"][
                i] + ", "

        article["authfullName_s"] = article["authfullName_s"][:-2]

        if sort_trigger:
            if "authIdHal_s" in article:
                if common_data(utln_rsr, article["authIdHal_s"]):

                    # colloque et posters
                    if article["docType_s"] == "COMM" or article["docType_s"] == "POSTER":
                        hceres_conf.append(article)
                    # art
                    if article["docType_s"] == "ART":
                        hceres_art.append(article)
                    # ouvrages, chapitres d'ouvrages et directions d'ouvrages
                    if article["docType_s"] == "COUV" or article["docType_s"] == "DOUV" or article[
                        "docType_s"] == "OUV":
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
            if article["docType_s"] == "COUV" or article["docType_s"] == "DOUV" or article["docType_s"] == "OUV":
                hceres_book.append(article)
            # hdr
            if article["docType_s"] == "HDR":
                print(article)
                hceres_hdr.append(article)

    art_df = pd.DataFrame(hceres_art)
    if len(art_df.index) > 0:
        art_df = art_df.sort_values(by=['publicationDateY_i'])

    book_df = pd.DataFrame(hceres_book)
    if len(book_df.index) > 0:
        book_df = book_df.sort_values(by=['publicationDateY_i'])

    conf_df = pd.DataFrame(hceres_conf)
    if len(conf_df.index) > 0:
        conf_df = conf_df.sort_values(by=['publicationDateY_i'])

    hceres_df = pd.DataFrame(hceres_hdr)
    if len(hceres_df.index) > 0:
        hceres_df = hceres_df.sort_values(by=['publicationDateY_i'])

    return art_df, book_df, conf_df, hceres_df
