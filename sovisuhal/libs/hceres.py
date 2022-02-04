import pandas as pd

from . import esActions

es = esActions.es_connector()

def sortReferences(articles, halStructId):
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
