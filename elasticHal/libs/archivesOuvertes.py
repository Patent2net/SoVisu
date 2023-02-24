import time

import networkx as nx
import requests
from SPARQLWrapper import JSON, SPARQLWrapper

# lets go
sparql = SPARQLWrapper("http://sparql.archives-ouvertes.fr/sparql")
sparql.setReturnFormat(JSON)


def get_halid_s(aurehal_id):
    """
    Récupération du authidhal_s associé au aurehal_id depuis HAL
    """

    sparql.setQuery(
        """
    select ?p ?o
    where  {
    <https://data.archives-ouvertes.fr/author/%s> ?p ?o
    }"""
        % aurehal_id
    )
    results = sparql.query().convert()
    ext_ids = [
        truc
        for truc in results["results"]["bindings"]
        if truc["p"]["value"] == "http://www.openarchives.org/ore/terms/isAggregatedBy"
    ]

    authidhal_s = ext_ids[0]["o"]["value"].split("/")[-1]
    return authidhal_s


def get_label(label, lang):
    """
    Récupére le nom complet d'un label en fonction de la langue associée
    """

    sparql.setQuery(
        """
        select ?p ?o
        where  {
        <https://data.archives-ouvertes.fr/subject/%s> ?p ?o
        }"""
        % label
    )
    results = sparql.query().convert()

    label = [
        truc["o"]["value"]
        for truc in results["results"]["bindings"]
        if truc["p"]["value"] == "http://www.w3.org/2004/02/skos/core#prefLabel"
        if truc["o"]["xml:lang"] == lang
    ]
    label_complet = label[0]
    return label_complet


def recup_individu(authidhal_s):
    """
    recupération des données d'un individu à partir de son authidhal_s
    """
    sparql.setQuery(
        """
select ?p ?o
where  {
<https://data.archives-ouvertes.fr/author/%s> ?p ?o
}"""
        % authidhal_s
    )
    donnee_individu = sparql.query().convert()
    # result in form of predicat, objet in a list in results['results']['bindings']
    return donnee_individu


def explore_broader(uri):
    """
    Recherche le domaine parent d'un domaine donné
    """

    sparql.setQuery(
        """
    select ?p ?o
    where  {<%s> ?p ?o }"""
        % uri
    )

    results = sparql.query().convert()

    concepts = [
        truc
        for truc in results["results"]["bindings"]
        if truc["p"]["value"] == "http://purl.org/dc/elements/1.1/identifier"
    ]
    # filtres par langues
    dico_top = dict()

    dico_top = [top["o"]["value"] for top in concepts]
    broader = [
        truc["o"]["value"]
        for truc in results["results"]["bindings"]
        if truc["p"]["value"] == "http://www.w3.org/2004/02/skos/core#broader"
    ]

    if len(broader) > 0:
        for broad in broader:
            dico_top.insert(0, explore_broader(broad))

    return dico_top


def extrait_sujets_domaines(data):
    """
    À partir des données d'un l'article, extrait les sujets et domaines
    """
    # extraction des résultats
    topics = [
        truc
        for truc in data["results"]["bindings"]
        if truc["p"]["value"] == "http://xmlns.com/foaf/0.1/topic_interest"
    ]
    sujets = [
        truc["o"]["value"]
        for truc in data["results"]["bindings"]
        if truc["p"]["value"] == "http://xmlns.com/foaf/0.1/interest"
    ]
    # récupération des langues

    for top in topics:
        if "xml:lang" not in top["o"]:
            top["o"]["xml:lang"] = "en"

    # topics = [top for top in topics if 'xml:lang' in top['o']]

    langues = list({top["o"]["xml:lang"] for top in topics})
    # filtres par langues
    dico_top = dict()

    for lang in langues:
        dico_top[lang] = [top["o"]["value"] for top in topics if top["o"]["xml:lang"] == lang]

    return dico_top, list(set(sujets))


def explain_domains(dom_uri):
    """
    Recherche le domaine parent d'un domaine dom_uri
    """
    sparql.setQuery(
        """
    prefix foaf: <http://xmlns.com/foaf/0.1/>
    prefix skos: <http://www.w3.org/2004/02/skos/core>
    select ?p ?o
    where  {
    <%s> ?p ?o
    }"""
        % dom_uri
    )

    results = sparql.query().convert()

    labels = dict()
    labels = [
        truc["o"]["value"]
        for truc in results["results"]["bindings"]
        if truc["p"]["value"] == "http://purl.org/dc/elements/1.1/identifier"
    ]
    broader = [
        truc["o"]["value"]
        for truc in results["results"]["bindings"]
        if truc["p"]["value"] == "http://www.w3.org/2004/02/skos/core#broader"
    ]

    if len(broader) > 0:
        tempo = []

        for broad in broader:
            res = explore_broader(broad)
            for r in res:
                tempo.append(r)

        tempo.append(labels)

        tempo_clone = []

        for temp in tempo:
            if isinstance(temp, str):
                tempo_clone.append([temp])
            else:
                tempo_clone.append(temp)

        return tempo_clone
    else:
        return [labels]


def get_concepts_and_keywords(aurehalid):
    """
    Récupère les concepts et mots-clés d'un auteur à partir de son aurehalid
    """

    keywords = []

    # extraction des sujets d'intérêt et domaines d'un chercheur
    data = recup_individu(aurehalid)

    sujets, domaines = extrait_sujets_domaines(data)
    domains = []

    # print(f"sujets:\n {sujets}\n domaines:\n {domaines}")
    # try:
    tree = ""
    for dom in domaines:
        domains.append(explain_domains(dom))

        # réseau json hiérarchiques
        #
        tree = nx.DiGraph()

        tree.add_node("Concepts")
        domains = [list(filter(lambda x: x is not None, truc)) for truc in domains]

        for dom1 in domains:
            tree.add_node(dom1[0][0])
            tree.add_edge("Concepts", dom1[0][0])
            if len(dom1) > 1:
                tree.add_node(dom1[1][0])
                tree.add_edge(dom1[0][0], dom1[1][0])
            if len(dom1) > 2:
                tree.add_node(dom1[2][0])
                tree.add_edge(dom1[1][0], dom1[2][0])
    if len(tree) == 0:  # ça s'est mal passé
        concepts_and_keywords = {"concepts": [], "keywords": []}
        return concepts_and_keywords
    else:
        concepts = nx.tree_data(tree, "Concepts")
    # with open(lang + "-concepts.json", "w", encoding='utf8') as ficRes:
    #     ficRes.write(str(nx.tree_data(tree, "Concepts")).replace("'", '"'))

    for children in concepts["children"]:
        children["label_en"] = get_label(children["id"], "en")
        children["label_fr"] = get_label(children["id"], "fr")
        children["state"] = "invalidated"
        if "children" in children:
            for subchildren in children["children"]:
                subchildren["label_en"] = get_label(subchildren["id"], "en")
                subchildren["label_fr"] = get_label(subchildren["id"], "fr")
                subchildren["state"] = "invalidated"
                if "children" in subchildren:
                    for subsubchildren in subchildren["children"]:
                        subsubchildren["label_en"] = get_label(subsubchildren["id"], "en")
                        subsubchildren["label_fr"] = get_label(subsubchildren["id"], "fr")
                        subsubchildren["state"] = "invalidated"

    for lang in sujets.keys():
        tree_words = nx.DiGraph()
        tree_words.add_node(lang)
        for kwd in sujets[lang]:
            tree_words.add_node(kwd)
            tree_words.add_edge(lang, kwd)
        keywords.append({"lang": lang, "keywords": nx.tree_data(tree_words, lang)})
        # with open(lang + "-words.json", "w", encoding='utf8') as ficRes:
        #    ficRes.write(str(nx.tree_data(treeWords, lang)).replace("'", '"'))
    concepts_and_keywords = {"concepts": concepts, "keywords": keywords}
    return concepts_and_keywords
    # except IndexError:
    #     concepts_and_keywords = {"concepts": [], "keywords": []}
    #     return concepts_and_keywords


def get_aurehalId(authIdHal_s):
    """
    get the aurehalId (authIdHal_i) of the searcher with authIdHal_s (halId_s)
    """
    if len(authIdHal_s) == 0:
        return 0
    url = (
        "https://api.archives-ouvertes.fr/search/?q=authIdHal_s:"
        + authIdHal_s
        + "&fl=authFullNamePersonIDIDHal_fs&rows=1&sort=docid%20asc"
    )

    res_status = False
    while res_status is False:
        # print(f"{authIdHal_s}")
        req = requests.request("GET", url)
        data = req.json()
        if "error" in data.keys():
            time.sleep(5)

        if "response" in data.keys():
            res_status = True

            sample = data["response"]["docs"][0]
            curr = 0
            for auth in sample["authFullNamePersonIDIDHal_fs"]:
                curr += 1
                if auth.split("_FacetSep_")[-1] == authIdHal_s:
                    break
            aurehalId = sample["authFullNamePersonIDIDHal_fs"][curr - 1].split("_FacetSep_")[1]
            return aurehalId
