import datetime


# Formatter for adding documents in the index
# TODO: Adjust all the formats for elastic_index_test2

def laboratory_format(notice):  # Up To Date (for now)
    labo_notice = {
        "category": "laboratory",
        "acronym": notice["acronym"],
        "halStructId": notice["halStructId"],
        "idRef": notice["idRef"],
        "label": notice["label"],
        "rsnr": notice["rsnr"],
        "structSirene": [notice["structSirene"]],
        "Created": datetime.datetime.now().isoformat(),
    }
    return labo_notice


def institution_format(notice):  # Up To Date (for now)
    institution_notice = {
        "category": "institution",
        "structSirene": notice["structSirene"],
        "acronym": notice["acronym"],
        "label": notice["label"],
        "domain": notice["domain"],
    }

    return institution_notice


# def publication_format(notice):
#     publication_notice = {
#         "category": "notice",
#         "authFirstName_s": notice["authFirstName_s"],
#         "authLastName_s": "",
#         "authFullName_s": "",
#         "authIdHal_i": "",
#         "authIdHal_s": "",
#         "contributorFullName_s": "",  # intéret à l'avoir ?
#         "country": "",
#         "country_collaboration": "",
#     }
#
#     return publication_notice

# TODO: connect to collect_doc
def publication_format(doc, added):
    # doc: gathered in base doc, added: made by sovisu. TEMPORARY
    publication_notice = {
        "docid": doc["docid"],
        "label_bibtex": doc["label_bibtex"],
        "openAccess_bool": doc["openAccess_bool"],
        "title_s": doc["title_s"],
        "fr_keyword_s": [],
        "fr_abstract_s": "",
        "authLastName_s": doc["authLastName_s"],
        "authFirstName_s": doc["authFirstName_s"],
        "authFullName_s": doc["authFullName_s"],
        "authIdHal_i": doc["authIdHal_i"],
        "authIdHal_s": doc["authIdHal_s"],
        "rteamStructCountry_s": doc["rteamStructCountry_s"],
        "structCountry_s": doc["structCountry_s"],
        "labStructId_i": doc["labStructId_i"],
        "labStructCountry_s": doc["labStructCountry_s"],
        "instStructCountry_s": doc["instStructCountry_s"],
        "rgrpInstStructCountry_s": doc["rgrpInstStructCountry_s"],
        "contributorFullName_s": doc["contributorFullName_s"],
        "language_s": doc["language_s"],
        "halId_s": doc["halId_s"],
        "version_i": doc["version_i"],
        "docType_s": doc["docType_s"],
        "bookTitle_s": "",
        "page_s": "",
        "modifiedDate_tdate": doc["modifiedDate_tdate"],
        "submittedDate_tdate": doc["submittedDate_tdate"],
        "producedDate_tdate": doc["producedDate_tdate"],
        "publicationDate_tdate": doc["publicationDate_tdate"],
        "publicationDateY_i": doc["publicationDateY_i"],
        "country": doc["country"],
        "deptStructCountry_s": doc["deptStructCountry_s"],
        "rgrpLabStructCountry_s": [],
        "country_collaboration": [],
        "country_s": [],
        "publicationLocation_s": [],
        "fr_entites": [],
        "fr_teeft_keywords": [],
        "Created": datetime.datetime.now().isoformat(),
        "harvested_from": "",
        "harvested_from_ids": [],
        "harvested_from_label": [],
        "records": [],
        "category": "notice-hal",
        "idhal": [],
        "postprint_embargo": "",
        "preprint_embargo": ""
    }
    return publication_notice


# def searcher_format(notice, orcid, labo_accro, structid, labhalid):
#     searcher_notice = {
#     "name": notice["attributes"]["displayName"],
#     "type": "Personnel",
#     "function": notice["attributes"]["typeEmploi"],
#     "mail": notice["attributes"]["mail"],
#     "orcId": orcid,
#     "lab": labo_accro,
#     "supannAffectation": "IMSIC;IUT TC",
#     "supannEntiteAffectationPrincipale": notice["attributes"]["supannEntiteAffectationPrincipale"],
#     "firstName": notice["attributes"]["displayName"].split(" ")[1],
#     "lastName": notice["attributes"]["displayName"].split(" ")[0],
#     "structSirene": structid,
#     "labHalId": labhalid,
#     "validated": False,
#     "ldapId": "dreymond",
#     "Created": datetime.datetime.now().isoformat(),
#     "idhal": "david-reymond",
#     "halId_s": "david-reymond",
#     "aurehalId": "7386",
#     "idRef": "test",
#     "axis": "IMSIC",
#     "category": "searcher"
#   }
#     return searcher_notice


def expertise_format(notice):
    expertise_notice = {
    "chemin": "",
    "label_en": "",
    "label_fr": "",
    "category": "",
    "referentiel": ""
    }
    return expertise_notice


# Mapping for the Index
def searcher_mapping():
    mapping = {

        "properties": {
            "Created": {
                "type": "date"
            },
            "SearcherProfile": {
                "type": "nested",
                "properties": {
                    "halId_s": {
                        "type": "text",
                        "fields": {
                            "keyword": {
                                "type": "keyword",
                                "ignore_above": 256
                            }
                        }
                    },
                    "ldapId": {
                        "type": "text",
                        "fields": {
                            "keyword": {
                                "type": "keyword",
                                "ignore_above": 256
                            }
                        }
                    },
                    "validated_concepts": {
                        "properties": {
                            "id": {
                                "type": "keyword"
                            },
                            "label_fr": {
                                "type": "text"
                            },
                            "label_en": {
                                "type": "text"
                            },
                            "children": {
                                "properties": {
                                    "id": {
                                        "type": "keyword"
                                    },
                                    "label_en": {
                                        "type": "text"
                                    },
                                    "label_fr": {
                                        "type": "text"
                                    }
                                }
                            },
                        }
                    }
                }
            },
            "aurehalId": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "axis": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "category": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "firstName": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "function": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "halId_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "idRef": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "lab": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "labHalId": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "lastName": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "ldapId": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "mail": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "name": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "orcId": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "structSirene": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "supannAffectation": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "supannEntiteAffectationPrincipale": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "type": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "validated": {
                "type": "boolean"
            }
        }

    }
    return mapping


def publication_mapping():
    mapping = {
        "properties": {
            "Created": {
                "type": "date"
            },
            "MDS": {
                "type": "float"
            },
            "SearcherProfile": {
                "type": "nested",
                "properties": {
                    "authorship": {
                        "type": "text",
                        "fields": {
                            "keyword": {
                                "type": "keyword",
                                "ignore_above": 256
                            }
                        }
                    },
                    "halId_s": {
                        "type": "text",
                        "fields": {
                            "keyword": {
                                "type": "keyword",
                                "ignore_above": 256
                            }
                        }
                    },
                    "ldapId": {
                        "type": "text",
                        "fields": {
                            "keyword": {
                                "type": "keyword",
                                "ignore_above": 256
                            }
                        }
                    },
                    "validated": {
                        "type": "text",
                        "fields": {
                            "keyword": {
                                "type": "keyword",
                                "ignore_above": 256
                            }
                        }
                    },
                    "validated_concepts": {
                        "type": "text",
                        "fields": {
                            "keyword": {
                                "type": "keyword",
                                "ignore_above": 256
                            }
                        }
                    }
                }
            },
            "authFirstName_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "authFullName_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "authIdHal_i": {
                "type": "long"
            },
            "authIdHal_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "authLastName_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "bookTitle_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "category": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "conferenceEndDate_tdate": {
                "type": "date"
            },
            "conferenceStartDate_tdate": {
                "type": "date"
            },
            "conferenceTitle_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "contributorFullName_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "country": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "country_collaboration": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "country_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "date_depot_oa": {
                "type": "date"
            },
            "defenseDate_tdate": {
                "type": "date"
            },
            "deptStructCountry_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "docType_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "docid": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "doiId_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "en_abstract_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "en_entites": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "en_keyword_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "en_subTitle_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "en_teeft_keywords": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "es_abstract_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "es_keyword_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "field_citation_ratio": {
                "type": "float"
            },
            "fileMain_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "fileType_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "fr_abstract_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "fr_entites": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "fr_keyword_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "fr_subTitle_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "fr_teeft_keywords": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "funding_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "halId_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "harvested_from": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "harvested_from_ids": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "instStructCountry_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "is_oa": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "isbn_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "issue_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "journalDate_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "journalIssn_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "journalPublisher_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "journalSherpaPostPrint_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "journalSherpaPostRest_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "journalSherpaPrePrint_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "journalSherpaPreRest_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "journalTitle_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "labStructCountry_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "labStructId_i": {
                "type": "long"
            },
            "label_bibtex": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "language_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "modifiedDate_tdate": {
                "type": "date"
            },
            "oa_host_type": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "oa_status": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "openAccess_bool": {
                "type": "boolean"
            },
            "page_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "postprint_embargo": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "preprint_embargo": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "producedDate_tdate": {
                "type": "date"
            },
            "pt_abstract_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "pt_keyword_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "pt_subTitle_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "publicationDateY_i": {
                "type": "long"
            },
            "publicationDate_tdate": {
                "type": "date"
            },
            "publicationLocation_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "rgrpInstStructCountry_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "rgrpLabStructCountry_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "rteamStructCountry_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "serie_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "structCountry_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "submittedDate_tdate": {
                "type": "date"
            },
            "times_cited": {
                "type": "long"
            },
            "title_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "version_i": {
                "type": "long"
            },
            "volume_s": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            }
        }
    }
    return mapping


def laboratories_mapping():
    mapping = {
        "properties": {
            "Created": {
                "type": "date"
            },
            "acronym": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "category": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "concepts": {
                "properties": {
                    "children": {
                        "properties": {
                            "children": {
                                "properties": {
                                    "children": {
                                        "properties": {
                                            "id": {
                                                "type": "text",
                                                "fields": {
                                                    "keyword": {
                                                        "type": "keyword",
                                                        "ignore_above": 256
                                                    }
                                                }
                                            },
                                            "label_en": {
                                                "type": "text",
                                                "fields": {
                                                    "keyword": {
                                                        "type": "keyword",
                                                        "ignore_above": 256
                                                    }
                                                }
                                            },
                                            "label_fr": {
                                                "type": "text",
                                                "fields": {
                                                    "keyword": {
                                                        "type": "keyword",
                                                        "ignore_above": 256
                                                    }
                                                }
                                            },
                                            "researchers": {
                                                "properties": {
                                                    "firstName": {
                                                        "type": "text",
                                                        "fields": {
                                                            "keyword": {
                                                                "type": "keyword",
                                                                "ignore_above": 256
                                                            }
                                                        }
                                                    },
                                                    "lastName": {
                                                        "type": "text",
                                                        "fields": {
                                                            "keyword": {
                                                                "type": "keyword",
                                                                "ignore_above": 256
                                                            }
                                                        }
                                                    },
                                                    "ldapId": {
                                                        "type": "text",
                                                        "fields": {
                                                            "keyword": {
                                                                "type": "keyword",
                                                                "ignore_above": 256
                                                            }
                                                        }
                                                    },
                                                    "state": {
                                                        "type": "text",
                                                        "fields": {
                                                            "keyword": {
                                                                "type": "keyword",
                                                                "ignore_above": 256
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    },
                                    "id": {
                                        "type": "text",
                                        "fields": {
                                            "keyword": {
                                                "type": "keyword",
                                                "ignore_above": 256
                                            }
                                        }
                                    },
                                    "label_en": {
                                        "type": "text",
                                        "fields": {
                                            "keyword": {
                                                "type": "keyword",
                                                "ignore_above": 256
                                            }
                                        }
                                    },
                                    "label_fr": {
                                        "type": "text",
                                        "fields": {
                                            "keyword": {
                                                "type": "keyword",
                                                "ignore_above": 256
                                            }
                                        }
                                    },
                                    "researchers": {
                                        "properties": {
                                            "firstName": {
                                                "type": "text",
                                                "fields": {
                                                    "keyword": {
                                                        "type": "keyword",
                                                        "ignore_above": 256
                                                    }
                                                }
                                            },
                                            "lastName": {
                                                "type": "text",
                                                "fields": {
                                                    "keyword": {
                                                        "type": "keyword",
                                                        "ignore_above": 256
                                                    }
                                                }
                                            },
                                            "ldapId": {
                                                "type": "text",
                                                "fields": {
                                                    "keyword": {
                                                        "type": "keyword",
                                                        "ignore_above": 256
                                                    }
                                                }
                                            },
                                            "state": {
                                                "type": "text",
                                                "fields": {
                                                    "keyword": {
                                                        "type": "keyword",
                                                        "ignore_above": 256
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            },
                            "id": {
                                "type": "text",
                                "fields": {
                                    "keyword": {
                                        "type": "keyword",
                                        "ignore_above": 256
                                    }
                                }
                            },
                            "label_en": {
                                "type": "text",
                                "fields": {
                                    "keyword": {
                                        "type": "keyword",
                                        "ignore_above": 256
                                    }
                                }
                            },
                            "label_fr": {
                                "type": "text",
                                "fields": {
                                    "keyword": {
                                        "type": "keyword",
                                        "ignore_above": 256
                                    }
                                }
                            },
                            "researchers": {
                                "properties": {
                                    "firstName": {
                                        "type": "text",
                                        "fields": {
                                            "keyword": {
                                                "type": "keyword",
                                                "ignore_above": 256
                                            }
                                        }
                                    },
                                    "lastName": {
                                        "type": "text",
                                        "fields": {
                                            "keyword": {
                                                "type": "keyword",
                                                "ignore_above": 256
                                            }
                                        }
                                    },
                                    "ldapId": {
                                        "type": "text",
                                        "fields": {
                                            "keyword": {
                                                "type": "keyword",
                                                "ignore_above": 256
                                            }
                                        }
                                    },
                                    "state": {
                                        "type": "text",
                                        "fields": {
                                            "keyword": {
                                                "type": "keyword",
                                                "ignore_above": 256
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "id": {
                        "type": "text",
                        "fields": {
                            "keyword": {
                                "type": "keyword",
                                "ignore_above": 256
                            }
                        }
                    }
                }
            },
            "halStructId": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "idRef": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "label": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "rsnr": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "structSirene": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            }
        }
    }
    return mapping


def institutions_mapping():
    mapping = {
        "properties": {
            "acronym": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "category": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "domain": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "label": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "structSirene": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            }
        }
    }

    return mapping


def expertises_mapping():
    mapping = {
        "properties": {
            "category": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "children": {
                "properties": {
                    "category": {
                        "type": "text",
                        "fields": {
                            "keyword": {
                                "type": "keyword",
                                "ignore_above": 256
                            }
                        }
                    },
                    "children": {
                        "properties": {
                            "id": {
                                "type": "text",
                                "fields": {
                                    "keyword": {
                                        "type": "keyword",
                                        "ignore_above": 256
                                    }
                                }
                            },
                            "label_en": {
                                "type": "text",
                                "fields": {
                                    "keyword": {
                                        "type": "keyword",
                                        "ignore_above": 256
                                    }
                                }
                            },
                            "label_fr": {
                                "type": "text",
                                "fields": {
                                    "keyword": {
                                        "type": "keyword",
                                        "ignore_above": 256
                                    }
                                }
                            }
                        }
                    },
                    "id": {
                        "type": "text",
                        "fields": {
                            "keyword": {
                                "type": "keyword",
                                "ignore_above": 256
                            }
                        }
                    },
                    "label_en": {
                        "type": "text",
                        "fields": {
                            "keyword": {
                                "type": "keyword",
                                "ignore_above": 256
                            }
                        }
                    },
                    "label_fr": {
                        "type": "text",
                        "fields": {
                            "keyword": {
                                "type": "keyword",
                                "ignore_above": 256
                            }
                        }
                    }
                }
            },
            "id": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "label_en": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "label_fr": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            }
        }
    }
    return mapping
