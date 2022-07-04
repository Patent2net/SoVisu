import requests
import grobid_tei_xml
import io
from elasticHal.libs import utils


def find_publications(idhal, field, increment=0):
    articles = []
    flags = 'docid,halId_s,docType_s,labStructId_i,authIdHal_s,authIdHal_i,authFullName_s,authFirstName_s,authLastName_s,doiId_s,journalIssn_s,' \
            'publicationDate_tdate,submittedDate_tdate,modifiedDate_tdate,producedDate_tdate,' \
            'fileMain_s,fileType_s,language_s,title_s,*_subTitle_s,*_abstract_s,*_keyword_s,label_bibtex,fulltext_t,' \
            'version_i,journalDate_s,journalTitle_s,journalPublisher_s,funding_s,' \
            'openAccess_bool,journalSherpaPostPrint_s,journalSherpaPrePrint_s,journalSherpaPostRest_s,journalSherpaPreRest_s,' \
            'bookTitle_s,journalTitle_s,volume_s,serie_s,page_s,issue_s,' \
            'conferenceTitle_s,conferenceStartDate_tdate,conferenceEndDate_tdate,' \
            'contributorFullName_s,' \
            'isbn_s,' \
            'publicationDateY_i,' \
            'defenseDate_tdate,' \
            'authId_i,' \
            'country_s, ' \
            'deptStructCountry_s,' \
            'labStructCountry_s,' \
            'location,' \
            'rgrpInstStructCountry_s,' \
            'rgrpLabStructCountry_s,' \
            'rteamStructCountry_s,' \
            'instStructCountry_s,' \
            'structCountry_s,' \
            'structCountry_t'

    req = requests.get(
        'http://api.archives-ouvertes.fr/search/?q=' + field + ':' + str(idhal) + '&fl=' + flags + '&start=' + str(
            increment))

    if req.status_code == 200:
        data = req.json()
        if "response" in data.keys():
            data = data['response']
            count = data['numFound']

            for article in data['docs']:
                facet_fields_list = ["country_s", "deptStructCountry_s", "labStructCountry_s", "location",
                                     "rgrpInstStructCountry_s", "rgrpLabStructCountry_s", "rteamStructCountry_s",
                                     "instStructCountry_s", "structCountry_s", "structCountry_t"]
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
            print('Error : wrong response from HAL API endpoint')
            return -1
    else:
        print('Error : can not reach HAL API endpoint')
        return articles


def get_content(hal_url):
    pdf_file = requests.get(hal_url)
    pdf_file.raise_for_status()

    grobid_resp = requests.post(
        "https://cloud.science-miner.com/grobid/api/processFulltextDocument",
        files={
            'input': utils.remove_page(pdf_file, [0]),  # remove first page (HAL header)
            'consolidate_Citations': 0,
            'includeRawCitations': 1,
        },
        timeout=60.0,
    )
    grobid_resp.raise_for_status()

    doc = grobid_tei_xml.parse_document_xml(grobid_resp.text)

    return doc.body
