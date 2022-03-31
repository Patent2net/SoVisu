from SPARQLWrapper import SPARQLWrapper, JSON
import networkx as nx


def cycle(liste):
    tempo = []
    if len(liste) < 1:
        return None
    else:
        taille = len(liste) - 1
        for indice in range(taille):
            tempo.append((liste[indice], liste[indice + 1]))
        return tempo


# lets go
sparql = SPARQLWrapper("http://sparql.archives-ouvertes.fr/sparql")
sparql.setReturnFormat(JSON)


def get_halid_s(aurehal_id):
    # start
    # auteur :Joseph
    # commentaire : Cette fonction prend en paramètre la valeur aurehal_id et retourne la valeur authIdHal_s associée
    # example: aurehal_id(826859)=>vanessa-richard
    # end
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
    # start
    # auteur :Joseph
    # commentaire : Cette fonction prend en paramètre la valeur label et lang et retourne le nom complet du label en fonction de la langue associée
    # example: get_label("phys","en") => Physics
    # end
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
    # start
    # auteur :Joseph
    # commentaire : Cette fonction prend en paramètre halId_s l'id d'un article et retourne sous forme de dictionnaire metadone_article qui regroupe l'ensemble des metadoné de l'article
    # example: get_article(702215) => {'head': {'link': [], 'vars': ['p', 'o']}, 'results': {'distinct': False, 'ordered': True, 'bindings': []}}
    # end
    """returns  Liste des métadonnées d'un document in sparlq dataarchive format"""
    sparql.setQuery("""select ?p ?o 
where {
 <https://data.archives-ouvertes.fr/document/%s> ?p ?o
} """ % halid_s)
    results = sparql.query().convert()
    metadone_article = results
    return metadone_article


def recup_individu(authidhal_s):
    # start
    # auteur :Joseph
    # commentaire : Cette fonction prend en paramètre authIdHal_s d'un cherhcheur et retourne sous forme de dictionnaire donnee_individu qui regroupe l'ensemble des données concernant le chercheur
    # example : recup_individu("vanessa-richard") => {'head': {'link': [], 'vars': ['p', 'o']}, 'results': {'distinct': False, 'ordered': True, 'bindings': [{'p': {'type': 'uri', 'value': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type'} ....
    # end
    sparql.setQuery("""
select ?p ?o
where  {
<https://data.archives-ouvertes.fr/author/%s> ?p ?o
}""" % authidhal_s)
    results = sparql.query().convert()
    # result in form of predicat, objet in a list in results['results']['bindings']
    donnee_individu = results
    return donnee_individu


def explore_broader(uri):

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
    """ inputs from recup_individu(halidint)
    halidint est un individu
    """
    # extraction des résultats
    topics = [truc for truc in data['results']['bindings'] if
              truc['p']['value'] == "http://xmlns.com/foaf/0.1/topic_interest"]
    sujets = [truc['o']['value'] for truc in data['results']['bindings'] if
              truc['p']['value'] == "http://xmlns.com/foaf/0.1/interest"]
    # récupération des langues

    # alaric : soit on considère que les mots qui n'ont pas de langue renseignée sont en anglais (j'ai constaté ça pour chl)
    # soit on les drop ?
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


def extrait_mots_cles(dat):
    """ inputs from get_article(halid)
    halid est un article
    """
    # extraction des résultats

    topics = [truc for truc in dat['results']['bindings'] if
              truc['p']['value'] == "http://purl.org/dc/elements/1.1/subject"]
    # sujets = [truc ['o']['value'] for truc in dat['results']['bindings'] if truc ['p']['value'] == "http://xmlns.com/foaf/0.1/interest"]
    # récupération des langues
    langues = list(set([top['o']['xml:lang'] for top in topics]))
    # filtres par langues
    dico_top = dict()

    for lang in langues:
        dico_top[lang] = [top['o']['value'] for top in topics if top['o']['xml:lang'] == lang]

    return dico_top


# tests
# Extraction des mots clés d'un article
# à faire valider par article
# res = get_article("hal-00000001v2")

# print (extrait_mots_cles (res) )
# print (extrait_mots_cles (res) )


def get_concepts_and_keywords(aurehalid):
    # start
    # auteur :Joseph
    # commentaire : Cette fonction prend en paramètre aurehal_id d'un chercheur et retourne sous forme de dictionnaire ConceptsAndKeywords qui regroupe l'ensemble des concept et donnée aborder par le chercheur
    # example : get_concepts_and_keywords(702215) => {'fr': ['Toxines', 'Génétique des populations', 'Écologie microbienne', 'Cyanobactéries']}
    # end

    keywords = []

    # extraction des sujets d'intérêt et domaines d'un chercheur
    data = recup_individu(aurehalid)

    sujets, domaines = extrait_sujets_domaines(data)
    domains = []

    print(sujets, domaines)
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
