from elasticsearch import helpers

from sovisuhal.libs import esActions

# Connect to DB
es = esActions.es_connector()

# Memo des pbs.
# Choix fait de se poser sur le ldapid --> pas de gestion des doublons type ex-doctorants
# si deux meme ldapid dans des index chercheurs différents alors
# memo du plus recent created seulement
# count = es.count(index="test_researchers")["count"]
# res = es.search(index="test_researchers", size=count)
# chercheurs = res["hits"]["hits"]

docmap = {
    "properties": {
        "docid": {
            "type": "long",
            "fields": {"keyword": {"type": "keyword", "ignore_above": 512}},
        },
        "en_keyword_s": {
            "type": "text",
            "fields": {"keyword": {"type": "keyword", "ignore_above": 512}},
        },
        "fr_entites": {
            "type": "text",
            "fields": {"keyword": {"type": "keyword", "ignore_above": 512}},
        },
        "en_entites": {
            "type": "text",
            "fields": {"keyword": {"type": "keyword", "ignore_above": 512}},
        },
        "fr_teeft_keywords": {
            "type": "text",  # formerly "string"
            "fields": {"keyword": {"type": "keyword", "ignore_above": 512}},
        },
        "en_teeft_keywords": {
            "type": "text",  # formerly "string"
            "fields": {"keyword": {"type": "keyword", "ignore_above": 512}},
        },
        "en_abstract_s": {
            "type": "text",  # formerly "string"
            "fields": {"keyword": {"type": "keyword", "ignore_above": 5000}},
        },
        "fr_abstract_s": {
            "type": "text",  # formerly "string"
            "fields": {"keyword": {"type": "keyword", "ignore_above": 5000}},
        },
        "it_abstract_s": {
            "type": "text",  # formerly "string"
            "fields": {"keyword": {"type": "keyword", "ignore_above": 5000}},
        },
        "es_abstract_s": {
            "type": "text",  # formerly "string"
            "fields": {"keyword": {"type": "keyword", "ignore_above": 5000}},
        },
        "pt_abstract_s": {
            "type": "text",  # formerly "string"
            "fields": {"keyword": {"type": "keyword", "ignore_above": 5000}},
        },
        "SearcherProfile": {
                "type": "nested",
                "properties": {
                    "ldapId": {
                        "type": "keyword"
                    },
                    "halId_s": {
                        "type": "keyword"
                    },
                    "validated_concepts": {
                        "type": "nested"
                    }
                    }
                }
    }
}

docmap['test_publications'] = {
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
            "type": "keyword"
          },
          "ldapId": {
            "type": "keyword"
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
            "type": "nested",
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
                    },
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
        "type": "long",
        "fields": {
          "keyword": {
            "type": "keyword",
            "ignore_above": 512
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
      "es_keyword_s": {
        "type": "text",
        "fields": {
          "keyword": {
            "type": "keyword",
            "ignore_above": 256
          }
        }
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
      "fr_keyword_s": {
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
            "fields": {"keyword": {"type": "keyword", "ignore_above": 512}},
        },
        "fr_entites": {
            "type": "text",
            "fields": {"keyword": {"type": "keyword", "ignore_above": 512}},
        },
        "en_entites": {
            "type": "text",
            "fields": {"keyword": {"type": "keyword", "ignore_above": 512}},
        },
        "fr_teeft_keywords": {
            "type": "text",  # formerly "string"
            "fields": {"keyword": {"type": "keyword", "ignore_above": 512}},
        },
        "en_teeft_keywords": {
            "type": "text",  # formerly "string"
            "fields": {"keyword": {"type": "keyword", "ignore_above": 512}},
        },
        "en_abstract_s": {
            "type": "text",  # formerly "string"
            "fields": {"keyword": {"type": "keyword", "ignore_above": 5000}},
        },
        "fr_abstract_s": {
            "type": "text",  # formerly "string"
            "fields": {"keyword": {"type": "keyword", "ignore_above": 5000}},
        },
        "it_abstract_s": {
            "type": "text",  # formerly "string"
            "fields": {"keyword": {"type": "keyword", "ignore_above": 5000}},
        },
        "es_abstract_s": {
            "type": "text",  # formerly "string"
            "fields": {"keyword": {"type": "keyword", "ignore_above": 5000}},
        },
        "pt_abstract_s": {
            "type": "text",  # formerly "string"
            "fields": {"keyword": {"type": "keyword", "ignore_above": 5000}},
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
      "journalSherpaPrePrint_s": {
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


docmap['test_researchers'] = {
    "properties": {
      "Created": {
        "type": "date"
      },
      "SearcherProfile": {
                "type": "text",
                "properties": {
                    "ldapId": {
                        "type": "keyword"
                    },
                    "halId_s": {
                        "type": "keyword"
                    },
                    "validated_concepts": {
                        "type": "nested"
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
      } # Pas plus judicieux de le mettre dans SearcherProfile ?
    }
  }



for ind in ["test_researchers", "test_publications" ]:
    if es.indices.exists(index=ind):
        compte = es.count(index=ind)["count"]
        docs = es.search(index=ind, size=compte)
        if len(docs["hits"]["hits"]) > 0:
            docu = docs["hits"]["hits"]
            print(len(docu), " docs. Destruction de :", "test_publications")
            es.options(ignore_status=[400, 404]).indices.delete(index=ind)
            dico = dict()
            dico["mappings"] = docmap [ind]
            dico["index"] = ind
            es.indices.create(**dico)
            if len(docu) > 10:
                # for doc in docu:
                #     doc["_source"]["docid"] = int(doc["_source"]["docid"])
                for indi in range(int(len(docu) // 50) + 1):
                    boutdeDoc = docu[indi * 50: indi * 50 + 50]
                    helpers.bulk(es, boutdeDoc, index=ind)
                resp = str(len(docu)) + " indexés "
            else:
                for doc in docu:
                    # doc["_source"]["docid"] = int(doc["_source"]["docid"])
                    es.options(request_timeout=200, retry_on_timeout=True, max_retries=5).index(
                        index=ind, id=doc["_id"], document=doc["_source"]
                    )
            resp = es.indices.refresh(index=ind)
            print(es.cluster.health())
            es.indices.put_mapping(index=ind, body=docmap [ind])
