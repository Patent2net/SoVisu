import io
import re
from datetime import datetime

import dateutil.parser
from dateutil.relativedelta import relativedelta
from nested_lookup import nested_lookup
from PyPDF2 import PdfFileReader, PdfFileWriter


def remove_page(pdf_file, pages):
    """
    Supprime des pages d'un pdf
    """
    infile = PdfFileReader(io.BytesIO(pdf_file.content))
    output = PdfFileWriter()
    for i in range(infile.getNumPages()):
        if i not in pages:
            p = infile.getPage(i)
            output.addPage(p)

    response_bytes_stream = io.BytesIO()
    output.write(response_bytes_stream)
    return response_bytes_stream.getvalue()


def should_be_open(doc):
    """
    Détermine si une notice devrait être ouverte
    """
    # -1 non
    # 1 oui
    # 0 no se
    # 2 déjà open
    # print(doc)
    if "fileMain_s" not in doc:
        if "journalSherpaPostPrint_s" in doc:
            if doc["journalSherpaPostPrint_s"] == "can":
                return 1
            if doc["journalSherpaPostPrint_s"] == "restricted":
                if "journalSherpaPostRest_s" in doc:
                    matches = re.finditer(
                        r"(\S+\s+){2}(?=embargo)",
                        doc["journalSherpaPostRest_s"].replace("[", " "),
                    )
                    maxi = 0

                    for m in matches:
                        c = m.group().split(" ")[0]
                        if c.isnumeric():
                            # check if sometimes there is year but atm, nope
                            if int(c) > maxi:
                                maxi = int(c)

                    p_date = dateutil.parser.parse(doc["publicationDate_tdate"]).replace(
                        tzinfo=None
                    )
                    curr_date = datetime.now()
                    diff = relativedelta(curr_date, p_date)

                    diff_months = diff.years * 12 + diff.months
                    if diff_months > maxi:
                        return 1
                    else:
                        return -1
                else:
                    return -1
            if doc["journalSherpaPostPrint_s"] == "cannot":
                return -1
        return 0
    return 2


def calculate_mds(doc):
    """
    Attribue un score à la qualité de description d'une notice.
    """
    score = 0

    if "title_s" in doc:
        has_title = True
    else:
        has_title = False

    if "doiId_s" in doc:
        has_doi = True
    else:
        has_doi = False

    if "publicationDate_tdate" in doc:
        has_publication_date = True
    else:
        has_publication_date = False

    keywords = nested_lookup(
        key="_keyword_s",
        document=doc,
        wild=True,
        with_keys=True,
    )

    if len(keywords) > 0:
        has_kw = True
    else:
        has_kw = False

    abstracts = nested_lookup(
        key="_abstract_s",
        document=doc,
        wild=True,
        with_keys=True,
    )

    if len(abstracts) > 0:
        has_abstract = True
    else:
        has_abstract = False

    if "fileMain_s" in doc:
        has_attached_file = True
    else:
        if doc["openAccess_bool"] == 1:
            has_attached_file = True
        else:
            has_attached_file = False

    if has_title:
        score += 1 * 0.8
    if has_publication_date:
        score += 1 * 0.2
    if has_kw:
        score += 1 * 1
    if has_abstract:
        score += 1 * 0.8
    if has_attached_file:
        score += 1 * 0.4
    if has_doi:
        score += 1 * 0.6

    return score * 100 / (0.8 + 0.2 + 1 + 0.8 + 0.4 + 0.6)


def append_to_tree(scope, rsr, tree, state):
    """
    Rajoute un domaine d'expertise à un arbre d'expertise
    """
    rsr_data = {
        "ldapId": rsr["ldapId"],
        "firstName": rsr["firstName"],
        "lastName": rsr["lastName"],
        "state": state,
    }
    rsr_id = rsr["ldapId"]

    sid = scope["id"].split(".")
    # print(f"\u00A0 \u21D2 \u00A0{scope}")

    scope_data = {
        "id": scope["id"],
        "label_fr": scope["label_fr"],
        "label_en": scope["label_en"],
        "children": [],
        "researchers": [rsr_data],
    }

    if len(sid) == 1:
        exists = False
        for child in tree["children"]:
            if sid[0] == child["id"] and "researchers" in child:
                for rsr in child["researchers"]:
                    rsr_exists = False
                    if rsr["ldapId"] == rsr_id:
                        rsr["state"] = state
                        rsr_exists = True
                if not rsr_exists:
                    child["researchers"].append(rsr_data)
                exists = True
        if not exists:
            tree["children"].append(scope_data)

    if len(sid) == 2:
        exists = False
        for child in tree["children"]:
            if sid[0] == child["id"] and "children" in child:
                for child1 in child["children"]:
                    if sid[0] + "." + sid[1] == child1["id"] and "researchers" in child1:
                        for rsr in child1["researchers"]:
                            rsr_exists = False
                            if rsr["ldapId"] == rsr_id:
                                rsr["state"] = state
                                rsr_exists = True
                        if not rsr_exists:
                            child1["researchers"].append(rsr_data)
                        exists = True

        if not exists:
            for child in tree["children"]:
                if "children" in child and sid[0] == child["id"]:
                    child["children"].append(scope_data)

    if len(sid) == 3:
        exists = False
        for child in tree["children"]:
            if sid[0] == child["id"] and "children" in child:
                for child1 in child["children"]:
                    if sid[0] + "." + sid[1] == child1["id"] and "children" in child1:
                        for child2 in child1["children"]:
                            if sid[0] + "." + sid[1] + "." + sid[2] == child2["id"]:
                                if "researchers" in child2:
                                    for rsr in child2["researchers"]:
                                        rsr_exists = False
                                        if rsr["ldapId"] == rsr_id:
                                            rsr["state"] = state
                                            rsr_exists = True
                                if not rsr_exists:
                                    child2["researchers"].append(rsr_data)
                                exists = True

        if not exists:
            for child in tree["children"]:
                if "children" in child and sid[0] == child["id"]:
                    for child1 in child["children"]:
                        if sid[0] + "." + sid[1] == child1["id"]:
                            child1["children"].append(scope_data)

    return tree


def filter_concepts(concepts, validated_ids):
    """
    Filtre les concepts qui ne sont pas dans la liste des concepts validés
    """
    if len(concepts) > 0:
        for children in concepts["children"]:
            if children["id"] in validated_ids:
                children["state"] = "validated"
            if "children" in children:
                for children1 in children["children"]:
                    if children1["id"] in validated_ids:
                        children1["state"] = "validated"
                    if "children" in children1:
                        for children2 in children1["children"]:
                            if children2["id"] in validated_ids:
                                children2["state"] = "validated"

    return concepts
