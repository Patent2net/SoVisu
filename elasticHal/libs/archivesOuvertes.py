from SPARQLWrapper import SPARQLWrapper, JSON
import networkx as nx

# lets go
sparql = SPARQLWrapper("http://sparql.archives-ouvertes.fr/sparql")
sparql.setReturnFormat(JSON)


def get_halid_s(aurehal_id):
    """
    Récupération du aurehal_id associé au authidhal_s dans HAL
    :param aurehal_id:
    :return:
    """

    sparql.setQuery("""
    select ?p ?o
    where  {
    <https://data.archives-ouvertes.fr/author/%s> ?p ?o
    }""" % aurehal_id)
    results = sparql.query().convert()
    ext_ids = [truc for truc in results['results']['bindings'] if truc['p']['value'] == "http://www.openarchives.org/ore/terms/isAggregatedBy"]

    authidhal_s = ext_ids[0]['o']['value'].split('/')[-1]
    return authidhal_s


def get_extid(authidhal_s):
    """
    Récupération du aurehal_id associé au authidhal_s
    :param authidhal_s:
    :return:
    """
    # Start
    # auteur :Joseph
    # commentaire : Cette fonction prend en paramètre la valeur authidhal_s et retourne la valeur aurehal_id associée
    # example : authIdHal_s(vanessa-richard)=>826859
    # end
    sparql.setQuery("""
    select ?p ?o
    where  {
    <https://data.archives-ouvertes.fr/author/%s> ?p ?o
    }""" % authidhal_s)
    results = sparql.query().convert()
    extids = [truc for truc in results['results']['bindings'] if
              truc['p']['value'] == "http://www.openarchives.org/ore/terms/aggregates"]
    aurehalid = int(extids[0]['o']['value'].rsplit('/', 1)[1])
    return aurehalid


def get_label(label, lang):
    """
    Récupére le nom complet d'un label en fonction de la langue associée
    :param label:
    :param lang:
    :return:
    """

    sparql.setQuery("""
        select ?p ?o
        where  {
        <https://data.archives-ouvertes.fr/subject/%s> ?p ?o
        }""" % label)
    results = sparql.query().convert()

    label = [truc['o']['value'] for truc in results['results']['bindings'] if
             truc['p']['value'] == "http://www.w3.org/2004/02/skos/core#prefLabel" if
             truc['o']['xml:lang'] == lang]
    label_complet = label[0]
    return label_complet


def get_article(halid_s):
    """
    Retourne la Liste des métadonnées d'un document dans SPARQL en format dataarchives
    :param halid_s:
    :return:
    """
    sparql.setQuery("""select ?p ?o 
where {
 <https://data.archives-ouvertes.fr/document/%s> ?p ?o
} """ % halid_s)
    metadone_article = sparql.query().convert()
    return metadone_article


def recup_individu(authidhal_s):
    """
    recupération des données d'un individu à partir de son authidhal_s
    :param authidhal_s:
    :return:
    """
    sparql.setQuery("""
select ?p ?o
where  {
<https://data.archives-ouvertes.fr/author/%s> ?p ?o
}""" % authidhal_s)
    donnee_individu = sparql.query().convert()
    # result in form of predicat, objet in a list in results['results']['bindings']
    return donnee_individu


def explore_broader(uri):
    """
    explore the broader concept of a concept
    :param uri:
    :return:
    """

    sparql.setQuery("""
    select ?p ?o
    where  {<%s> ?p ?o }""" % uri)

    results = sparql.query().convert()

    concepts = [truc for truc in results['results']['bindings'] if
                truc['p']['value'] == "http://purl.org/dc/elements/1.1/identifier"]
    # filtres par langues
    dico_top = dict()

    dico_top = [top['o']['value'] for top in concepts]
    broader = [truc['o']['value'] for truc in results['results']['bindings'] if
               truc['p']['value'] == "http://www.w3.org/2004/02/skos/core#broader"]

    if len(broader) > 0:
        for broad in broader:
            dico_top.insert(0, explore_broader(broad))

    return dico_top


def extrait_sujets_domaines(data):
    """
    TODO: à vérifier
    à partir des données de l'article, extrait les sujets et domaines
    :param data:
    :return:
    """
    # extraction des résultats
    topics = [truc for truc in data['results']['bindings'] if
              truc['p']['value'] == "http://xmlns.com/foaf/0.1/topic_interest"]
    sujets = [truc['o']['value'] for truc in data['results']['bindings'] if
              truc['p']['value'] == "http://xmlns.com/foaf/0.1/interest"]
    # récupération des langues

    for top in topics:
        if 'xml:lang' not in top['o']:
            top['o']['xml:lang'] = 'en'

    # topics = [top for top in topics if 'xml:lang' in top['o']]

    langues = list(set([top['o']['xml:lang'] for top in topics]))
    # filtres par langues
    dico_top = dict()

    for lang in langues:
        dico_top[lang] = [top['o']['value'] for top in topics if top['o']['xml:lang'] == lang]

    return dico_top, list(set(sujets))


def explain_domains(dom_uri):
    """
    Recherche le domaine parent d'un domaine dom_uri
    :param dom_uri:
    :return:
    """
    sparql.setQuery("""
    prefix foaf: <http://xmlns.com/foaf/0.1/>
    prefix skos: <http://www.w3.org/2004/02/skos/core>
    select ?p ?o
    where  {
    <%s> ?p ?o
    }""" % dom_uri)

    results = sparql.query().convert()

    labels = dict()
    labels = [truc['o']['value'] for truc in results['results']['bindings'] if
              truc['p']['value'] == "http://purl.org/dc/elements/1.1/identifier"]
    broader = [truc['o']['value'] for truc in results['results']['bindings'] if
               truc['p']['value'] == "http://www.w3.org/2004/02/skos/core#broader"]

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
    :param aurehalid:
    :return:
    """

    keywords = []

    # extraction des sujets d'intérêt et domaines d'un chercheur
    data = recup_individu(aurehalid)

    sujets, domaines = extrait_sujets_domaines(data)
    domains = []

    # print(f"sujets:\n {sujets}\n domaines:\n {domaines}")
    try:
        tree = ''
        for dom in domaines:
            domains.append(explain_domains(dom))

            # réseau json hiérarchiques
            #
            tree = nx.DiGraph()

            tree.add_node('Concepts')
            domains = [list(filter(lambda x: x != None, truc)) for truc in domains]

            for dom1 in domains:
                tree.add_node(dom1[0][0])
                tree.add_edge('Concepts', dom1[0][0])
                if len(dom1) > 1:
                    tree.add_node(dom1[1][0])
                    tree.add_edge(dom1[0][0], dom1[1][0])
                if len(dom1) > 2:
                    tree.add_node(dom1[2][0])
                    tree.add_edge(dom1[1][0], dom1[2][0])

        concepts = nx.tree_data(tree, "Concepts")
        # with open(lang + "-concepts.json", "w", encoding='utf8') as ficRes:
        #     ficRes.write(str(nx.tree_data(tree, "Concepts")).replace("'", '"'))

        for children in concepts['children']:
            children['label_en'] = get_label(children['id'], 'en')
            children['label_fr'] = get_label(children['id'], 'fr')
            children['state'] = 'invalidated'
            if 'children' in children:
                for subchildren in children['children']:
                    subchildren['label_en'] = get_label(subchildren['id'], 'en')
                    subchildren['label_fr'] = get_label(subchildren['id'], 'fr')
                    subchildren['state'] = 'invalidated'
                    if 'children' in subchildren:
                        for subsubchildren in subchildren['children']:
                            subsubchildren['label_en'] = get_label(subsubchildren['id'], 'en')
                            subsubchildren['label_fr'] = get_label(subsubchildren['id'], 'fr')
                            subsubchildren['state'] = 'invalidated'

        for lang in sujets.keys():

            tree_words = nx.DiGraph()
            tree_words.add_node(lang)
            for kwd in sujets[lang]:
                tree_words.add_node(kwd)
                tree_words.add_edge(lang, kwd)
            keywords.append({'lang': lang, 'keywords': nx.tree_data(tree_words, lang)})
            # with open(lang + "-words.json", "w", encoding='utf8') as ficRes:
            #    ficRes.write(str(nx.tree_data(treeWords, lang)).replace("'", '"'))
        concepts_and_keywords = {'concepts': concepts, 'keywords': keywords}
        return concepts_and_keywords

    except:
        concepts_and_keywords = {'concepts': [], 'keywords': []}
        return concepts_and_keywords
