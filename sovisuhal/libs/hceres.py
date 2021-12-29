import pandas as pd


def sortReferences(articles):

    hceres_art = []
    hceres_book = []
    hceres_conf = []
    hceres_hdr = []

    for article in articles:

        article["authfullName_s"] = ""

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
                article["conferenceDate_s"] = tmp_start[2] + "-" + tmp_start[1] + "-" + tmp_start[0] + ", " + tmp_end[2] + "-" + tmp_end[1] + "-" + tmp_end[0]
            else:
                article["conferenceDate_s"] = tmp_start[2] + "-" + tmp_start[1] + "-" + tmp_start[0]
        else:
            if 'conferenceEndDate_tdate' in article:
                article["conferenceDate_s"] = tmp_end[2] + "-" + tmp_end[1] + "-" + tmp_end[0]

        if "defenseDate_tdate" in article:
            article["defenseDate_tdate_s"] = article["defenseDate_tdate"][0:9]

        article["title_s"] = article["title_s"][0]

        for i in range(len(article["authFirstName_s"])):
            article["authfullName_s"] += article["authLastName_s"][i].upper() + " " + article["authFirstName_s"][i] + ", "

        article["authfullName_s"] = article["authfullName_s"][:-2]

        print(article["authfullName_s"])

        # colloque et posters
        if article["docType_s"] == "COMM" or article["docType_s"] == "POSTER":
            hceres_conf.append(article)

        # art
        if article["docType_s"] == "ART":
            hceres_art.append(article)
        # ouvrages, chapitres d'ouvrages et directions d'ouvrages
        if article["docType_s"] == "COUV" or article["docType_s"] == "DOUV" or article["docType_s"] == "OUV":
            hceres_book.append(article)


    art_df = pd.DataFrame(hceres_art)
    art_df = art_df.sort_values(by=['publicationDateY_i'])

    book_df = pd.DataFrame(hceres_book)
    book_df = book_df.sort_values(by=['publicationDateY_i'])

    conf_df = pd.DataFrame(hceres_conf)
    conf_df = conf_df.sort_values(by=['publicationDateY_i'])

    return art_df, book_df, conf_df