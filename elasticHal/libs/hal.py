import grobid_tei_xml
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import datetime

from elasticHal.libs import utils

retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["HEAD", "GET", "DELETE", "PUT", "OPTIONS"],
)
adapter = HTTPAdapter(max_retries=retry_strategy)
http = requests.Session()
http.mount("https://", adapter)
http.mount("http://", adapter)


def find_publications(idhal, field, increment=0):
    """
    Cherche les publications d'un auteur dans HAL à partir de son IDHAL
    """
    articles = []
    flags = (
        "docid,halId_s,docType_s,labStructId_i,authIdHal_s,authIdHal_i,authFullName_s,authFirstName_s,authLastName_s,doiId_s,journalIssn_s,"
        "publicationDate_tdate,submittedDate_tdate,modifiedDate_tdate,producedDate_tdate,"
        "fileMain_s,fileType_s,language_s,title_s,*_subTitle_s,*_abstract_s,*_keyword_s,label_bibtex,fulltext_t,"
        "version_i,journalDate_s,journalTitle_s,journalPublisher_s,funding_s,"
        "openAccess_bool,journalSherpaPostPrint_s,journalSherpaPrePrint_s,journalSherpaPostRest_s,journalSherpaPreRest_s,"
        "bookTitle_s,journalTitle_s,volume_s,serie_s,page_s,issue_s,"
        "conferenceTitle_s,conferenceStartDate_tdate,conferenceEndDate_tdate,"
        "contributorFullName_s,"
        "isbn_s,"
        "publicationDateY_i,"
        "defenseDate_tdate,"
        "authId_i,"
        "country_s, "
        "deptStructCountry_s,"
        "labStructCountry_s,"
        "location,"
        "rgrpInstStructCountry_s,"
        "rgrpLabStructCountry_s,"
        "rteamStructCountry_s,"
        "instStructCountry_s,"
        "structCountry_s,"
        "structCountry_t"
    )

    req = http.get(
        f"http://api.archives-ouvertes.fr/search/?q={field}:{str(idhal)}&fl={flags}&start={str(increment)}&sort=docid%20asc"
    )

    if req.status_code == 200:
        data = req.json()
        if "response" in data.keys():
            data = data["response"]
            count = data["numFound"]

            for article in data["docs"]:
                facet_fields_list = [
                    "country_s",
                    "deptStructCountry_s",
                    "labStructCountry_s",
                    "location",
                    "rgrpInstStructCountry_s",
                    "rgrpLabStructCountry_s",
                    "rteamStructCountry_s",
                    "instStructCountry_s",
                    "structCountry_s",
                    "structCountry_t",
                ]
                country_list = list()
                for facet in facet_fields_list:
                    if facet in article.keys():
                        if type(article[facet]) == list:
                            country_list.extend(article[facet])
                        else:
                            country_list.append(article[facet])

                country_list = list(set(country_list))
                country_list_upper = [country.upper() for country in country_list]
                article["country"] = country_list_upper

                articles.append(article)
            if (count > 30) and (increment < count):
                increment += 30
                tmp_articles = find_publications(idhal, field, increment=increment)
                if tmp_articles != -1:
                    for tmp_article in tmp_articles:

                        articles.append(tmp_article)
                return articles
            else:
                return articles
        else:
            print("Error : wrong response from HAL API endpoint")
            return -1
    else:
        print("Error : can not reach HAL API endpoint")
        return articles


def get_content(hal_url):
    """
    Récupère le contenu d'un article HAL à partir de son URL
    """
    pdf_file = http.get(hal_url)
    pdf_file.raise_for_status()

    grobid_resp = requests.post(
        "https://cloud.science-miner.com/grobid/api/processFulltextDocument",
        files={
            "input": utils.remove_page(pdf_file, [0]),  # remove first page (HAL header)
            "consolidate_Citations": 0,
            "includeRawCitations": 1,
        },
        timeout=60.0,
    )
    grobid_resp.raise_for_status()

    doc = grobid_tei_xml.parse_document_xml(grobid_resp.text)

    return doc.body


def find_structures_entities(search_filter="parentIdref_s", search_value="031122337", struct_type="laboratory"):
    # TODO: Rajouter un élément pour récuperer tous les éléments et pas juste une partie. Utiliser count et se baser sur collecte_docs
    """
    Get the structures entities based on a known parameter or a known parameter of the parent.
    For more information about parameters:
    https://api.archives-ouvertes.fr/docs/ref/?resource=structure&schema=fields#fields

    arguments:
    search_filter: the key used to get the information, if you want the childs of a known structure, use parent* keys
    search_value: the matching value to be found
    struct_type: the category of structure (laboratory, institution, researchteam, department, regrouplaboratory).

    examples:
    get the data about UTLN institution:
    https://api.archives-ouvertes.fr/ref/structure/?wt=json&q=acronym_s:UTLN+valid_s:VALID+type_s:institution&fl=*

    get the data about UTLN children laboratories:
    https://api.archives-ouvertes.fr/ref/structure/?wt=json&q=parentAcronym_s:UTLN+type_s:laboratory+valid_s:VALID&fl=*
    """
    structures_entities = []

    flags = (
        "docid,label_s,acronym_s,name_s,idRef_s, country_s,type_s,"  # Base information about doc
        "idref_s,isni_s,rnsr_s,ror_s,"  # information about optional ids
        "parentDocid_i,parentAcronym_s,parentName_s,parentCountry_s,parentType_s,parentIdref_s,parentIsni_s,parentRnsr_s,parentRor_s,"  # informations about parent structrures
    )
    request_entities = http.get(
        f"https://api.archives-ouvertes.fr/ref/structure/?wt=json&q={search_filter}:{search_value}+type_s:{struct_type}+valid_s:VALID&fl={flags}"
    )

    if request_entities.status_code == 200:
        entities_data = request_entities.json()
        if "response" in entities_data.keys():
            entities_data = entities_data["response"]
            count = entities_data["numFound"]

            for entity in entities_data["docs"]:
                entity["sovisu_category"] = entity["type_s"]
                entity["sovisu_referentiel"] = "hal"
                entity["sovisu_created"] = datetime.datetime.now().isoformat()
                structures_entities.append(entity)

    return structures_entities


# TODO: faire une fonction pour récupérer l'ensemble des documents d'une collection labo
#  -https://api.archives-ouvertes.fr/search/IMSIC/
#  - api/search/{lab_acronym}/{filters}
#  NE PAS Passer par l'accronyme mais par le labHalId - la collection Hal
def get_searcher_hal_data(idhal_s):
    req = http.get(
        f"https://api.archives-ouvertes.fr/ref/author/?wt=json&q=valid_s:PREFERRED+idHal_s:{idhal_s}&fl=*"
    )
    searcher_data = req.json()
    searcher_data = searcher_data["response"]["docs"][0]

    return searcher_data
