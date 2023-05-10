import datetime


def laboratory_format(notice, concept_tree):
    labo_notice = {
        "_id": notice["halStructId"],
        "category": "laboratory",
        "acronym": notice["acronym"],
        "halStructId": notice["halStructId"],
        "idRef": notice["idRef"],
        "label": notice["label"],
        "rsnr": notice["rsnr"],
        "structSirene": [notice["structSirene"]],
        "guidingKeywords": [],
        "concepts": concept_tree,
        "SearcherProfile": [],
        "Created": datetime.datetime.now().isoformat(),
    }
    return labo_notice


def institution_format(notice):
    institution_notice = {
        "_id": notice["structSirene"],
        "category": "institution",
        "structSirene": notice["structSirene"],
        "acronym": notice["acronym"],
        "label": notice["label"],
        "domain": notice["domain"],
    }

    return institution_notice


def publication_format(notice):
    publication_notice = {
        "_id": notice["docid"],
        "category": "notice",
        "authFirstName_s": notice["authFirstName_s"],
        "authLastName_s": "",
        "authFullName_s": "",
        "authIdHal_i": "",
        "authIdHal_s": "",
        "contributorFullName_s": "",  # intéret à l'avoir ?
        "country": "",
        "country_collaboration": "",
    }

    return publication_notice
